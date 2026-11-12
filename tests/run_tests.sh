#!/usr/bin/env bash
# Builds and runs the host tests for the protocol core. Requires g++ (C++17).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/gen.py >/dev/null
g++ -std=c++17 -Wall -Wextra -Werror -Icomponents/thermia_bus \
    components/thermia_bus/thermia_core.cpp components/thermia_bus/registers_gen.cpp tests/test_core.cpp -o /tmp/thermia_core_tests
/tmp/thermia_core_tests
