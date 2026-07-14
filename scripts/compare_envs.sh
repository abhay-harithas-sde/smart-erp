#!/usr/bin/env bash
# Compare local render.env with a provided Render env JSON (or file of KEY=VALUE lines)
# Usage: ./compare_envs.sh [render_env_file] [render_remote_env_file]
# Example: ./compare_envs.sh ../render.env render_dashboard.env

left=${1:-../render.env}
right=${2:-render_dashboard.env}

if [ ! -f "$left" ]; then
  echo "Local env file $left not found." >&2
  exit 1
fi

if [ ! -f "$right" ]; then
  echo "Remote env file $right not found. Create it with KEY=VALUE lines exported from Render." >&2
  exit 1
fi

# Normalize to KEY=VALUE and sort
sed '/^\s*#/d;/^\s*$/d' "$left" | sort > /tmp/left.env
sed '/^\s*#/d;/^\s*$/d' "$right" | sort > /tmp/right.env

echo "Only in local ($left):"
comm -23 /tmp/left.env /tmp/right.env || true

echo
echo "Only in remote ($right):"
comm -13 /tmp/left.env /tmp/right.env || true

echo
echo "Differences (keys in both but values differ):"
join -t '=' -o 1.1,1.2,2.2 <(awk -F= '{print $1"="$2}' /tmp/left.env | sort -t= -k1,1) <(awk -F= '{print $1"="$2}' /tmp/right.env | sort -t= -k1,1) | awk -F' ' '$2!=$3 {print $1"\n  local: "$2"\n  remote: "$3"\n"}' || true

rm -f /tmp/left.env /tmp/right.env
