#!/bin/bash
# cs-task.sh — Claude Squad 任务桥接
# 在 Claude Squad 里新建 agent 时用这个脚本自动拿 task queue 的下一个任务
#
# Usage (在 Claude Squad TUI 里):
#   按 n → 输入 prompt → 粘贴: $(cs-task next)
#   或直接: cs-task run  → 自动拿下一个 pending 任务并输出 prompt
#
# Usage (手动):
#   cs-task next          — 显示下一个 pending 任务的 prompt
#   cs-task list          — 显示所有 pending 任务
#   cs-task claim ID      — 认领并标记任务为 in_progress

QUEUE_URL="http://localhost:8742"

case "${1:-next}" in
  next)
    # 获取最高优先级的 pending 任务
    TASK=$(curl --noproxy '*' -s "$QUEUE_URL/tasks/list?status=pending" 2>/dev/null | \
      python3 -c "
import json, sys
data = json.load(sys.stdin)
tasks = data.get('tasks', [])
if not tasks:
    print('NO_PENDING_TASKS')
    sys.exit(0)
# Sort by priority then id
tasks.sort(key=lambda t: (t.get('priority','P9'), t.get('id',999)))
t = tasks[0]
print(f\"Task #{t['id']} [{t['priority']}]: {t['title']}\")
print(f\"Objective: {t.get('objective', t['title'])}\")
" 2>/dev/null)

    if [ "$TASK" = "NO_PENDING_TASKS" ]; then
      echo "No pending tasks in queue."
    else
      echo "$TASK"
    fi
    ;;

  list)
    curl --noproxy '*' -s "$QUEUE_URL/tasks/summary-text" 2>/dev/null
    ;;

  claim)
    ID="${2}"
    [ -z "$ID" ] && echo "Usage: cs-task claim TASK_ID" && exit 1
    curl --noproxy '*' -s -X POST "$QUEUE_URL/tasks/update" \
      -H "Content-Type: application/json" \
      -d "{\"task_id\": $ID, \"status\": \"in_progress\"}" 2>/dev/null
    echo "Task #$ID claimed"
    ;;

  done)
    ID="${2}"
    SUMMARY="${3:-completed}"
    [ -z "$ID" ] && echo "Usage: cs-task done TASK_ID [summary]" && exit 1
    curl --noproxy '*' -s -X POST "$QUEUE_URL/tasks/update" \
      -H "Content-Type: application/json" \
      -d "{\"task_id\": $ID, \"status\": \"done\", \"result_summary\": \"$SUMMARY\"}" 2>/dev/null
    echo "Task #$ID marked done"
    ;;

  *)
    cat <<'HELP'
cs-task — Task Queue 桥接

  cs-task next       下一个 pending 任务
  cs-task list       所有任务状态
  cs-task claim ID   认领任务（标记 in_progress）
  cs-task done ID    完成任务
HELP
    ;;
esac
