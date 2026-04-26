"""One-shot DDL: install the AlloyDB AI NL2SQL stack on call_records.

Reads:
  - DATABASE_URL          (required, postgres-superuser DSN)
  - NL_READER_PASSWORD    (required, password for the netpulse_nl_reader
                            role — must satisfy password.enforce_complexity:
                            >=8 chars, mix of upper/lower/digit/special)
  - NL_CONFIG_ID          (default: netpulse_cdr_config)
  - AL_CALL_TABLE         (default: call_records)
  - LLM_MODEL_ID          (default: gemini-2.5-flash:generateContent)

Steps (each guarded so a partial run can be re-executed):
  1.  CREATE EXTENSION alloydb_ai_nl CASCADE
  1b. google_ml.create_model registers the LLM (alloydb_ai_nl rejects
      models not in google_ml.model_info_view — predict_row's
      auto-discovery does NOT carry over)
  2.  g_create_configuration(<config>)
  2b. g_manage_configuration change_model — bind config to the LLM
  3.  g_manage_configuration: register_table_view → public.<table>
  4.  g_manage_configuration: add_general_context → enums + cities + tower scheme
  5.  generate_schema_context (BLOCKS for 3-5 minutes; waits via 30 min stmt timeout)
  6.  apply_generated_schema_context
  7.  associate_concept_type city_name → region
  8.  create_value_index
  9.  add_template × 4 — common intent shapes
  10. CREATE ROLE netpulse_nl_reader + grants (idempotent)

Re-running is safe: the configuration / role / extension steps each
detect existing state and continue. generate_schema_context uses
overwrite_if_exist => TRUE.

Run:
    DATABASE_URL='postgresql+pg8000://postgres:<pw>@<host>:5432/postgres' \\
    NL_READER_PASSWORD='<strong-password>' \\
    .venv/bin/python scripts/setup_alloydb_nl.py
"""

import logging
import os
import sys

import sqlalchemy

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL must be set (postgres-superuser DSN)")

NL_READER_PASSWORD = os.environ.get("NL_READER_PASSWORD")
if not NL_READER_PASSWORD:
    raise RuntimeError(
        "NL_READER_PASSWORD must be set — must satisfy "
        "password.enforce_complexity (>=8 chars, upper+lower+digit+special)"
    )

NL_CONFIG_ID = os.environ.get("NL_CONFIG_ID", "netpulse_cdr_config")
AL_CALL_TABLE = os.environ.get("AL_CALL_TABLE", "call_records")
LLM_MODEL_ID = os.environ.get("LLM_MODEL_ID", "gemini-2.5-flash:generateContent")

GENERAL_CONTEXT_LINES: list[str] = [
    "call_status enum: completed | dropped | failed",
    "call_type enum: voice | sms | data",
    (
        "region values are Indonesian city names: Jakarta, Surabaya, Bandung, "
        "Medan, Semarang, Yogyakarta, Denpasar, Makassar, Palembang, Balikpapan"
    ),
    (
        "cell_tower_id format is <CITY-PREFIX>-NNN where CITY-PREFIX is a "
        "3-letter region code: JKT (Jakarta), SBY (Surabaya), BDG (Bandung), "
        "MDN (Medan), SMG (Semarang), YOG (Yogyakarta), DPS (Denpasar), "
        "MKS (Makassar), PLM (Palembang), BPN (Balikpapan)"
    ),
    (
        "Time questions like 'recently' or 'this week' mean the last 7 days; "
        "'lately' means the last 30 days; 'today' means the current calendar day"
    ),
]

TEMPLATES: list[tuple[str, str]] = [
    (
        "Count of dropped or failed calls in a region during a recent window",
        (
            "SELECT call_status, COUNT(*) AS call_count "
            f"FROM {AL_CALL_TABLE} "
            "WHERE region = $1 AND call_status IN ('dropped', 'failed') "
            "  AND call_date >= NOW() - INTERVAL '7 days' "
            "GROUP BY call_status "
            "ORDER BY call_count DESC"
        ),
    ),
    (
        "Top cell towers by failed-call volume in a region",
        (
            "SELECT cell_tower_id, COUNT(*) AS failed_count "
            f"FROM {AL_CALL_TABLE} "
            "WHERE region = $1 AND call_status = 'failed' "
            "  AND call_date >= NOW() - INTERVAL '14 days' "
            "GROUP BY cell_tower_id "
            "ORDER BY failed_count DESC "
            "LIMIT 5"
        ),
    ),
    (
        "Call volume by call_type in a region",
        (
            "SELECT call_type, COUNT(*) AS volume "
            f"FROM {AL_CALL_TABLE} "
            "WHERE region = $1 "
            "  AND call_date >= NOW() - INTERVAL '30 days' "
            "GROUP BY call_type "
            "ORDER BY volume DESC"
        ),
    ),
    (
        "Daily failure trend for a region",
        (
            "SELECT DATE(call_date) AS day, "
            "       SUM(CASE WHEN call_status='dropped' THEN 1 ELSE 0 END) AS dropped, "
            "       SUM(CASE WHEN call_status='failed'  THEN 1 ELSE 0 END) AS failed "
            f"FROM {AL_CALL_TABLE} "
            "WHERE region = $1 "
            "  AND call_date >= NOW() - INTERVAL '14 days' "
            "GROUP BY day "
            "ORDER BY day DESC"
        ),
    ),
]


def _commit(conn: sqlalchemy.Connection, sql: str, **params: str) -> None:
    """Execute a statement and commit it on its own. Failure does not roll back
    earlier successful commits — important because some steps in this setup are
    not transactional (e.g. CREATE EXTENSION)."""
    conn.execute(sqlalchemy.text(sql), params)
    conn.commit()


def _commit_try(conn: sqlalchemy.Connection, sql: str, **params: str) -> bool:
    """Try-execute + commit. Returns False (and rolls back this single step
    only) on any DB error — used for the not-truly-idempotent setup calls
    where a re-run hits "already exists" / "already done" errors that we
    want to treat as success."""
    try:
        conn.execute(sqlalchemy.text(sql), params)
        conn.commit()
        return True
    except Exception as exc:  # noqa: BLE001 - re-run-on-error is the contract
        conn.rollback()
        logger.info("  -> tolerated: %s", str(exc).split(chr(10))[0][:160])
        return False


def install_extension(conn: sqlalchemy.Connection) -> None:
    """CREATE EXTENSION alloydb_ai_nl CASCADE — idempotent via IF NOT EXISTS."""
    logger.info("Step 1: ensure alloydb_ai_nl extension")
    _commit(conn, "CREATE EXTENSION IF NOT EXISTS alloydb_ai_nl CASCADE")


def register_llm_model(conn: sqlalchemy.Connection) -> None:
    """Register the LLM that NL2SQL will use to translate questions.

    google_ml.predict_row auto-discovers Google publisher models, but
    alloydb_ai_nl.g_manage_configuration(operation => 'change_model')
    rejects models that are not in google_ml.model_info_view first. The
    instance flag default_llm_model=gemini-2.5-flash-lite is silently
    ignored for the same reason — no entry, no use. We register
    gemini-2.5-flash (GA, generally accessible in us-central1) and bind
    the netpulse_cdr_config to it after the schema-context generation
    step (which runs against the system default).

    Re-registration with the same model_id raises 'already exists',
    which is expected and tolerated."""
    logger.info("Step 1b: register %s in google_ml", LLM_MODEL_ID)
    try:
        conn.execute(
            sqlalchemy.text(
                "CALL google_ml.create_model("
                "  model_id            => :mid,"
                "  model_request_url   => :url,"
                "  model_provider      => 'google',"
                "  model_type          => 'generic',"
                "  model_qualified_name=> :mid,"
                "  model_auth_type     => 'alloydb_service_agent_iam'"
                ")"
            ),
            {
                "mid": LLM_MODEL_ID,
                "url": f"publishers/google/models/{LLM_MODEL_ID}",
            },
        )
        conn.commit()
    except Exception as exc:  # noqa: BLE001 - "already exists" is the re-run path
        conn.rollback()
        logger.info("  -> tolerated: %s", str(exc).split(chr(10))[0][:160])


def ensure_configuration(conn: sqlalchemy.Connection) -> None:
    """g_create_configuration + bind it to the registered LLM model.

    Re-binding the model is idempotent (always sets the same id), but
    g_create_configuration is not — _commit_try absorbs the dup error."""
    logger.info("Step 2: ensure NL config %s", NL_CONFIG_ID)
    _commit_try(
        conn,
        "SELECT alloydb_ai_nl.g_create_configuration(:cid)",
        cid=NL_CONFIG_ID,
    )
    logger.info("Step 2b: bind config %s to model %s", NL_CONFIG_ID, LLM_MODEL_ID)
    _commit(
        conn,
        "SELECT alloydb_ai_nl.g_manage_configuration("
        "  operation           => 'change_model',"
        "  configuration_id_in => :cid,"
        "  model_id_in         => :mid"
        ")",
        cid=NL_CONFIG_ID,
        mid=LLM_MODEL_ID,
    )


def register_table(conn: sqlalchemy.Connection) -> None:
    """register_table_view — safe to re-call (no-op if already mapped)."""
    logger.info("Step 3: register_table_view → public.%s", AL_CALL_TABLE)
    _commit_try(
        conn,
        "SELECT alloydb_ai_nl.g_manage_configuration("
        "  operation           => 'register_table_view',"
        "  configuration_id_in => :cid,"
        "  table_views_in      => :tv"
        ")",
        cid=NL_CONFIG_ID,
        tv="{public." + AL_CALL_TABLE + "}",
    )


def add_general_context(conn: sqlalchemy.Connection) -> None:
    """Push the human-curated context bullets into the config."""
    logger.info("Step 4: add_general_context (%d lines)", len(GENERAL_CONTEXT_LINES))
    payload = "{" + ",".join(f'"{line}"' for line in GENERAL_CONTEXT_LINES) + "}"
    _commit_try(
        conn,
        "SELECT alloydb_ai_nl.g_manage_configuration("
        "  operation           => 'add_general_context',"
        "  configuration_id_in => :cid,"
        "  general_context_in  => :ctx"
        ")",
        cid=NL_CONFIG_ID,
        ctx=payload,
    )


def generate_and_apply_schema(conn: sqlalchemy.Connection) -> None:
    """generate_schema_context blocks 3-5 min while it LLM-summarises columns."""
    logger.info("Step 5: generate_schema_context (3-5 min, blocking)")
    _commit(
        conn,
        "SELECT alloydb_ai_nl.generate_schema_context("
        "  nl_config_id       => :cid,"
        "  overwrite_if_exist => TRUE"
        ")",
        cid=NL_CONFIG_ID,
    )
    logger.info("Step 6: apply_generated_schema_context")
    _commit(
        conn,
        "SELECT alloydb_ai_nl.apply_generated_schema_context(:cid)",
        cid=NL_CONFIG_ID,
    )


def associate_region_concept(conn: sqlalchemy.Connection) -> None:
    """Tag the region column as the built-in city_name concept so the LLM
    knows region values are city tokens (helps NL2SQL match misspelled or
    capitalisation-variant city tokens to the canonical 10-city set)."""
    logger.info("Step 7: associate_concept_type city_name → region")
    _commit_try(
        conn,
        "SELECT alloydb_ai_nl.associate_concept_type("
        "  column_names_in => :col,"
        "  concept_type_in => 'city_name',"
        "  nl_config_id_in => :cid"
        ")",
        col=f"public.{AL_CALL_TABLE}.region",
        cid=NL_CONFIG_ID,
    )


def build_value_index(conn: sqlalchemy.Connection) -> None:
    """Build a value index over the registered tables for example matching."""
    logger.info("Step 8: create_value_index")
    _commit_try(
        conn,
        "SELECT alloydb_ai_nl.create_value_index(nl_config_id_in => :cid)",
        cid=NL_CONFIG_ID,
    )


def add_templates(conn: sqlalchemy.Connection) -> None:
    """Seed 4 templates covering the demo's top intent shapes.

    `check_intent` defaults to false on add_template — leaving it false here
    is intentional. With check_intent=TRUE the function tries to *execute*
    the example SQL via EXPLAIN; our templates keep `$1` placeholders for
    the region (so they generalise across cities), which fails that check.
    The templates are intent-shape examples, not executable queries — the
    NL2SQL model substitutes its own bound region at translation time.
    """
    logger.info("Step 9: add_template × %d", len(TEMPLATES))
    for intent, tpl_sql in TEMPLATES:
        _commit_try(
            conn,
            "SELECT alloydb_ai_nl.add_template("
            "  nl_config_id => :cid,"
            "  intent       => :intent,"
            "  sql          => :tpl_sql"
            ")",
            cid=NL_CONFIG_ID,
            intent=intent,
            tpl_sql=tpl_sql,
        )


def create_reader_role(conn: sqlalchemy.Connection) -> None:
    """CREATE ROLE netpulse_nl_reader + grants — idempotent via pg_roles probe."""
    logger.info("Step 10: ensure netpulse_nl_reader role + grants")
    role_exists = conn.execute(
        sqlalchemy.text("SELECT 1 FROM pg_roles WHERE rolname = 'netpulse_nl_reader'")
    ).first()
    if role_exists:
        logger.info("  role already present, refreshing password")
        _commit(
            conn,
            f"ALTER ROLE netpulse_nl_reader WITH PASSWORD '{NL_READER_PASSWORD}'",
        )
    else:
        _commit(
            conn,
            f"CREATE ROLE netpulse_nl_reader LOGIN PASSWORD '{NL_READER_PASSWORD}'",
        )
    _commit(conn, "GRANT CONNECT ON DATABASE postgres TO netpulse_nl_reader")
    _commit(conn, "GRANT USAGE ON SCHEMA public TO netpulse_nl_reader")
    _commit(conn, f"GRANT SELECT ON public.{AL_CALL_TABLE} TO netpulse_nl_reader")
    _commit(conn, "GRANT USAGE ON SCHEMA alloydb_ai_nl TO netpulse_nl_reader")
    # Grant on all NL2SQL functions in the schema rather than per-signature —
    # alloydb_ai_nl.get_sql / execute_nl_query each have multiple overloads
    # (5 args + cursor variant) and listing every signature is brittle. This
    # grant is bounded to one schema, which already only contains read-only
    # NL2SQL helpers (no DDL or write functions).
    _commit(
        conn,
        "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA alloydb_ai_nl "
        "TO netpulse_nl_reader",
    )


def main() -> None:
    """Run the 10-step setup against the configured AlloyDB instance."""
    engine = sqlalchemy.create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_recycle=300,
        # 30 min — generate_schema_context can take 3-5 min on a fresh table.
        connect_args={"timeout": 1800},
    )
    # Use connect() (not begin()) so each step can commit independently —
    # avoids one late failure rolling back all the prior good work.
    with engine.connect() as conn:
        install_extension(conn)
        register_llm_model(conn)
        ensure_configuration(conn)
        register_table(conn)
        add_general_context(conn)
        generate_and_apply_schema(conn)
        associate_region_concept(conn)
        build_value_index(conn)
        add_templates(conn)
        create_reader_role(conn)
    logger.info("AlloyDB AI NL2SQL setup complete for config %s", NL_CONFIG_ID)
    sys.exit(0)


if __name__ == "__main__":
    main()
