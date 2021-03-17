#!/bin/bash

# Provide a unified interface for the different logging
# utilities CI providers offer. If unavailable, provide
# a compatible fallback (e.g. bare `echo xxxxxx`).

function startgroup {
    # Start a foldable group of log lines
    # Pass a single argument, quoted

    # Ccheck the status of xtrace
    # We want to disable it if it's ON to
    # prevent duplicated group tags
    setx_was_on=false
    if [ -o xtrace ]; then
        set +x  # disable temporarily
        setx_was_on=true
    fi
    case ${CI:-} in
        azure )
            echo "##[group]$1";;
        travis )
            echo "$1"
            echo -en 'travis_fold:start:'"${1// /}"'\\r';;
        * )
            echo "$1";;
    esac

    # If it was on, reenable
    $setx_was_on && set -x
}

function endgroup {
    # End a foldable group of log lines
    # Pass a single argument, quoted

    setx_was_on=false
    if [ -o xtrace ]; then
        set +x
        setx_was_on=true
    fi
    case ${CI:-} in
        azure )
            echo "##[endgroup]";;
        travis )
            echo -en 'travis_fold:end:'"${1// /}"'\\r';;
    esac

    $setx_was_on && set -x
}
