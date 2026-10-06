#!/bin/sh
# Lemo-Opuscar wrapper: pins the library to Hermes' data dir, then runs the upstream setup.sh.
#   opuscar.sh                 refresh library, print LIB=<path>
#   opuscar.sh deps [voice] [music]
#   opuscar.sh demo <slug>     add one style's demo source (reference only)
export LEMO_OPUSCAR_HOME="${LEMO_OPUSCAR_HOME:-$HOME/.hermes/data/motion-graphics/opuscar}"
exec sh "$(dirname "$0")/setup.sh" "$@"
