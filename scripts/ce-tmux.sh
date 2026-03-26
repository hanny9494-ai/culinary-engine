#!/bin/bash
# ce-tmux.sh — Culinary Engine tmux 任务控制台
#
# Usage:
#   ce-tmux                   — 进入 ce session
#   ce-tmux dashboard         — 分屏看所有 agent + 状态
#   ce-tmux agent NAME        — 开交互式 agent 窗口
#   ce-tmux status            — 列出窗口 + task queue
#   ce-tmux kill NAME         — 关闭窗口

SESSION="ce"
LOG_DIR="$HOME/culinary-engine/reports"

ensure_session() {
  tmux has-session -t $SESSION 2>/dev/null || \
    tmux new-session -d -s $SESSION -n main
}

attach_or_switch() {
  if [ -n "$TMUX" ]; then
    tmux switch-client -t "$SESSION"
  else
    tmux attach -t "$SESSION"
  fi
}

case "${1:-enter}" in
  enter)
    ensure_session
    attach_or_switch
    ;;

  dashboard)
    ensure_session

    # 删旧 dashboard
    tmux kill-window -t "$SESSION:dashboard" 2>/dev/null
    tmux new-window -t $SESSION -n dashboard

    # pane 0: 状态面板（紧凑）
    tmux send-keys -t "$SESSION:dashboard.0" "watch -n 8 -t 'curl --noproxy \"*\" -s http://localhost:8742/tasks/summary-text 2>/dev/null | head -25'" Enter

    # 收集所有任务窗口名
    TASK_WINDOWS=$(tmux list-windows -t $SESSION -F "#{window_name}" 2>/dev/null | grep -vE "^(main|dashboard|orchestrator|explorer|researcher|logs)$")

    # 为每个任务窗口加一个 pane
    PANE_IDX=1
    for WIN in $TASK_WINDOWS; do
      LOG_FILE="$LOG_DIR/orchestrator_${WIN}.log"
      tmux split-window -t "$SESSION:dashboard" -v -l 5 2>/dev/null || break
      if [ -f "$LOG_FILE" ]; then
        tmux send-keys -t "$SESSION:dashboard.$PANE_IDX" "printf '\\033[1;36m${WIN}\\033[0m\\n' && tail -f $LOG_FILE | tail -3" Enter
      else
        tmux send-keys -t "$SESSION:dashboard.$PANE_IDX" "printf '\\033[1;36m${WIN}\\033[0m\\n' && while true; do tmux capture-pane -t '$SESSION:$WIN' -p -S -3 2>/dev/null; sleep 5; clear; done" Enter
      fi
      PANE_IDX=$((PANE_IDX + 1))
    done

    # tiled 自动平铺
    tmux select-layout -t "$SESSION:dashboard" tiled 2>/dev/null
    # 缩小最小 pane 尺寸
    tmux set-window-option -t "$SESSION:dashboard" pane-border-format " #{pane_index}: #{pane_title} " 2>/dev/null

    tmux select-window -t "$SESSION:dashboard"
    attach_or_switch
    ;;

  agent)
    NAME="${2:-researcher}"
    ensure_session

    if tmux list-windows -t $SESSION -F "#{window_name}" 2>/dev/null | grep -q "^${NAME}$"; then
      echo "Window '$NAME' exists, switching"
    else
      tmux new-window -t $SESSION -n "$NAME"
      tmux send-keys -t "$SESSION:$NAME" "export no_proxy=localhost,127.0.0.1 http_proxy= https_proxy=" Enter
      tmux send-keys -t "$SESSION:$NAME" "cd ~/culinary-engine && clear" Enter
      # 检查是否有对应的 agent 定义文件
      AGENT_FILE="$HOME/culinary-engine/.claude/agents/${NAME}.md"
      if [ -f "$AGENT_FILE" ]; then
        tmux send-keys -t "$SESSION:$NAME" "claude --agent $NAME" Enter
      else
        tmux send-keys -t "$SESSION:$NAME" "echo 'No agent definition for $NAME, starting default claude'" Enter
        tmux send-keys -t "$SESSION:$NAME" "claude" Enter
      fi
    fi

    tmux select-window -t "$SESSION:$NAME"
    attach_or_switch
    ;;

  status)
    echo "══ tmux: $SESSION ══"
    tmux list-windows -t $SESSION -F "  #{window_index}: #{window_name} (#{window_panes}p)" 2>/dev/null || echo "  Not running"
    echo
    curl --noproxy '*' -s http://localhost:8742/tasks/summary-text 2>/dev/null || echo "  Queue not reachable"
    ;;

  kill)
    NAME="${2}"
    [ -z "$NAME" ] && echo "Usage: ce-tmux kill NAME" && exit 1
    tmux kill-window -t "$SESSION:$NAME" 2>/dev/null && echo "Killed $NAME" || echo "Not found"
    ;;

  *)
    cat <<'HELP'
ce-tmux 控制台

  ce-tmux              进入 session（Ctrl-b w 选窗口）
  ce-tmux dashboard    分屏看所有 agent + 状态面板
  ce-tmux agent NAME   开交互窗口（explorer/researcher）
  ce-tmux status       列出窗口 + queue
  ce-tmux kill NAME    关窗口

Ctrl-b w = 列窗口 | Ctrl-b d = 退出 | Ctrl-b [ = 滚动
HELP
    ;;
esac
