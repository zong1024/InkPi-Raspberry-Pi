#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

bash "${SCRIPT_DIR}/stop_backend_stack.sh"
bash "${SCRIPT_DIR}/start_backend_stack.sh"
bash "${SCRIPT_DIR}/health_check_stack.sh" backend
