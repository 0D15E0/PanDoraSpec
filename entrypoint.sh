#!/bin/bash
set -e

# Construct the command
CMD="pandoraspec $1 --vendor $2"

if [ -n "$3" ]; then
  CMD="$CMD --key $3"
fi

if [ -n "$4" ]; then
  CMD="$CMD --config $4"
fi

if [ -n "$5" ]; then
  CMD="$CMD --base-url $5"
fi

CMD="$CMD --format $6"

if [ -n "$7" ]; then
  CMD="$CMD --output $7"
fi

# Run it
exec $CMD
