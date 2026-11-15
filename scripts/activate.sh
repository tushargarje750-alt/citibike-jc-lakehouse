# Run once per new terminal window, from the repo root:
#
#     source scripts/activate.sh
#
# It activates the Python virtualenv and exports the variables in .env
# so dbt can read them. It never prints the token.

if [ ! -d .venv ] || [ ! -f .env ]; then
  echo "ERROR: run this from the repo root; it needs .venv/ and .env (copy .env.example to .env)."
  return 1 2>/dev/null || exit 1
fi

. .venv/bin/activate

set -a
. ./.env
set +a

case "${DBT_ENV_SECRET_DATABRICKS_TOKEN:-}" in
  ""|dapiREPLACE_ME) echo "WARNING: DBT_ENV_SECRET_DATABRICKS_TOKEN is not set in .env yet." ;;
esac

echo "OK: venv active, .env loaded (host: ${DBT_DATABRICKS_HOST:-not set}, catalog: ${DBT_CATALOG:-not set})"
