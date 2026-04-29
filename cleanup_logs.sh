#!/bin/bash
# Delete successful log files older than 24 hours
find /tmp/autotube_*.log -type f -mtime +1 -delete 2>/dev/null  
