#!/usr/bin/env bash
# Shared system-library path fix for numpy/pandas/freqtrade.
# Nix containers often hide libstdc++.so.6 / libz.so.1 from the loader.
# Safe to source anywhere: only prepends dirs that exist, never duplicates.
if [[ -z "${AIRSI_ENV_LIBS_LOADED:-}" ]]; then
  for _airsi_lib in \
    "${AIRSI_GCC_LIB:-/nix/store/0gnnf8s259nn28s41zs4rhpbfqm148rm-gcc-11.4.0-lib/lib}" \
    "${AIRSI_ZLIB_LIB:-/nix/store/026hln0aq1hyshaxsdvhg0kmcm6yf45r-zlib-1.2.13/lib}"; do
    if [[ -d "$_airsi_lib" ]]; then
      if [[ -z "${LD_LIBRARY_PATH:-}" ]]; then
        export LD_LIBRARY_PATH="$_airsi_lib"
      else
        case ":$LD_LIBRARY_PATH:" in
          *":$_airsi_lib:"*) ;;
          *) export LD_LIBRARY_PATH="$_airsi_lib:$LD_LIBRARY_PATH" ;;
        esac
      fi
    fi
  done
  unset _airsi_lib
  export AIRSI_ENV_LIBS_LOADED=1
fi
