#!/bin/bash
# Self-contained Ghidra decompiler for eu5.exe. Everything under .toolbin/re
# (gitignored); nothing installed system-wide.
set -e
cd "$(dirname "$0")"
RE=$(pwd)
if [ ! -d jdk-21.0.12.1+1 ]; then
  echo "== downloading JDK 21"
  curl -sL --max-time 900 -o jdk.tar.gz "https://api.adoptium.net/v3/binary/latest/21/ga/mac/aarch64/jdk/hotspot/normal/eclipse"
  tar xzf jdk.tar.gz && rm jdk.tar.gz
fi
if [ ! -d ghidra_12.1.3_PUBLIC ]; then
  echo "== downloading Ghidra 12.1.3 (543MB)"
  curl -sL --max-time 2400 -o ghidra.zip "https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_12.1.3_build/ghidra_12.1.3_PUBLIC_20260817.zip"
  unzip -q ghidra.zip && rm ghidra.zip
fi
G=$RE/ghidra_12.1.3_PUBLIC
if [ ! -x $G/Ghidra/Features/Decompiler/os/mac_arm_64/decompile ]; then
  echo "== building the decompiler (no mac binary ships with Ghidra)"
  ( cd $G/Ghidra/Features/Decompiler/src/decompile/cpp && make -j8 ghidra_opt >/dev/null 2>&1 )
  mkdir -p $G/Ghidra/Features/Decompiler/os/mac_arm_64
  cp $G/Ghidra/Features/Decompiler/src/decompile/cpp/ghidra_opt \
     $G/Ghidra/Features/Decompiler/os/mac_arm_64/decompile
  chmod +x $G/Ghidra/Features/Decompiler/os/mac_arm_64/decompile
fi
echo "== ready"
