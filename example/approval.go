package feishu

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"regexp"
	"sync"
	"time"

	"github.com/Gordon/OpsClaw/internal/schema"
)

// ApprovalResult 审批结果
type ApprovalResult struct {
	Allowed bool
	Reason  string
}

// ApprovalDetail 审批请求的原始信息（用于更新卡片时回显）
type ApprovalDetail struct {
	ToolName string
	ArgsStr  string
}

// ApprovalManager 管理审批流程的 Channel 中枢
type ApprovalManager struct {
	mu             sync.RWMutex
	pendingTasks   map[string]chan ApprovalResult
	pendingDetails map[string]*ApprovalDetail // 保存原始审批信息，供卡片回显
}

// GlobalApprovalMgr 全局审批管理器单例
var GlobalApprovalMgr = &ApprovalManager{
	pendingTasks:   make(map[string]chan ApprovalResult),
	pendingDetails: make(map[string]*ApprovalDetail),
}

// WaitForApproval 阻塞等待审批结果
// taskID: 任务唯一标识（通常使用 ToolCall.ID）
// toolName: 工具名称
// args: 工具参数
// reporter: 用于发送审批卡片的 Reporter
func (am *ApprovalManager) WaitForApproval(taskID string, toolName string, args string, reporter *FeishuReporter) ApprovalResult {
	// 创建结果通道（容量 1 防止死锁）
	ch := make(chan ApprovalResult, 1)

	am.mu.Lock()
	am.pendingTasks[taskID] = ch
	am.pendingDetails[taskID] = &ApprovalDetail{ToolName: toolName, ArgsStr: args}
	am.mu.Unlock()

	// 发送审批请求
	am.sendApprovalRequest(taskID, toolName, args, reporter)

	// 阻塞等待，超时 5 分钟自动拒绝
	select {
	case result := <-ch:
		am.mu.Lock()
		delete(am.pendingTasks, taskID)
		// 注意：pendingDetails 由回调方消费后删除，不在此清理
		am.mu.Unlock()
		return result
	case <-time.After(5 * time.Minute):
		am.mu.Lock()
		delete(am.pendingTasks, taskID)
		delete(am.pendingDetails, taskID) // 超时无回调，直接清理
		am.mu.Unlock()
		log.Printf("[Approval] 任务 %s 审批超时，自动拒绝\n", taskID)
		return ApprovalResult{Allowed: false, Reason: "审批超时（5分钟）"}
	}
}

// GetAndRemoveApprovalDetail 获取并移除审批详情（供卡片回调使用）
func (am *ApprovalManager) GetAndRemoveApprovalDetail(taskID string) *ApprovalDetail {
	am.mu.Lock()
	defer am.mu.Unlock()
	detail, exists := am.pendingDetails[taskID]
	if exists {
		delete(am.pendingDetails, taskID)
	}
	return detail
}

// ResolveApproval 处理审批回调
func (am *ApprovalManager) ResolveApproval(taskID string, allowed bool, reason string) {
	am.mu.RLock()
	ch, exists := am.pendingTasks[taskID]
	am.mu.RUnlock()

	if !exists {
		log.Printf("[Approval] 未找到待审批任务: %s\n", taskID)
		return
	}

	ch <- ApprovalResult{Allowed: allowed, Reason: reason}
}

// sendApprovalRequest 发送审批卡片消息
func (am *ApprovalManager) sendApprovalRequest(taskID string, toolName string, args string, reporter *FeishuReporter) {
	// 使用独立 context 发送卡片（避免依赖已过期的事件 context）
	sendCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if reporter != nil {
		toolCall := schema.ToolCall{
			ID:        taskID,
			Name:      toolName,
			Arguments: json.RawMessage(args),
		}
		log.Printf("[Approval] 发送审批卡片: %s (工具=%s)\n", taskID, toolName)
		reporter.SendApprovalCard(sendCtx, toolCall, args)
	} else {
		log.Printf("[Approval] 无 Reporter，打印到终端:\n工具: %s\n任务ID: %s\n参数: %s\n", toolName, taskID, truncate(args, 500))
	}
}

// buildApprovalCardJSON 构建飞书交互式审批卡片
func buildApprovalCardJSON(toolCall schema.ToolCall, argsStr string) string {
	card := map[string]interface{}{
		"config": map[string]interface{}{
			"wide_screen_mode": true,
		},
		"header": map[string]interface{}{
			"template": "orange",
			"title": map[string]interface{}{
				"tag":     "plain_text",
				"content": "⚠️ 安全审批请求",
			},
		},
		"elements": []interface{}{
			// 工具信息
			map[string]interface{}{
				"tag": "div",
				"text": map[string]interface{}{
					"tag": "lark_md",
					"content": fmt.Sprintf("**工具:** %s\n**任务ID:** %s",
						toolCall.Name, toolCall.ID),
				},
			},
			// 分割线
			map[string]interface{}{
				"tag": "hr",
			},
			// 参数内容
			map[string]interface{}{
				"tag": "div",
				"text": map[string]interface{}{
					"tag":     "lark_md",
					"content": fmt.Sprintf("**参数:**\n```%s```", truncate(argsStr, 500)),
				},
			},
			// 分割线
			map[string]interface{}{
				"tag": "hr",
			},
			// 按钮行
			map[string]interface{}{
				"tag": "action",
				"actions": []interface{}{
					map[string]interface{}{
						"tag":  "button",
						"text": map[string]interface{}{"tag": "plain_text", "content": "✅ 允许一次"},
						"type": "primary",
						"value": map[string]interface{}{
							"task_id": toolCall.ID,
							"action":  "approve_once",
						},
					},
					map[string]interface{}{
						"tag":  "button",
						"text": map[string]interface{}{"tag": "plain_text", "content": "📋 本次会话"},
						"type": "default",
						"value": map[string]interface{}{
							"task_id": toolCall.ID,
							"action":  "approve_session",
						},
					},
					map[string]interface{}{
						"tag":  "button",
						"text": map[string]interface{}{"tag": "plain_text", "content": "♾️ 始终允许"},
						"type": "default",
						"value": map[string]interface{}{
							"task_id": toolCall.ID,
							"action":  "approve_always",
						},
					},
					map[string]interface{}{
						"tag":  "button",
						"text": map[string]interface{}{"tag": "plain_text", "content": "❌ 拒绝"},
						"type": "danger",
						"value": map[string]interface{}{
							"task_id": toolCall.ID,
							"action":  "reject",
						},
					},
				},
			},
		},
	}

	bs, err := json.Marshal(card)
	if err != nil {
		log.Printf("[Approval] 构建卡片 JSON 失败: %v\n", err)
		return "{}"
	}
	return string(bs)
}

// buildApprovalResultCard 构建审批结果卡片（用于回调更新原卡片）
// headerTemplate: "green"=通过, "red"=拒绝
// resultLabel: 结果显示文本
func buildApprovalResultCard(taskID string, detail *ApprovalDetail, resultLabel string, headerTemplate string, operatorID string) map[string]interface{} {
	// 构建工具信息和参数回显
	toolInfo := fmt.Sprintf("**任务ID:** %s", taskID)
	argsDisplay := ""
	if detail != nil {
		toolInfo = fmt.Sprintf("**工具:** %s\n**任务ID:** %s", detail.ToolName, taskID)
		argsDisplay = fmt.Sprintf("**参数:**\n```%s```", truncate(detail.ArgsStr, 500))
	}

	// 操作人信息
	operatorInfo := ""
	if operatorID != "" {
		operatorInfo = fmt.Sprintf("**操作人:** %s", operatorID)
	}

	elements := []interface{}{
		// 工具信息
		map[string]interface{}{
			"tag": "div",
			"text": map[string]interface{}{
				"tag":     "lark_md",
				"content": toolInfo,
			},
		},
	}

	// 参数内容（如果有）
	if argsDisplay != "" {
		elements = append(elements, map[string]interface{}{"tag": "hr"})
		elements = append(elements, map[string]interface{}{
			"tag": "div",
			"text": map[string]interface{}{
				"tag":     "lark_md",
				"content": argsDisplay,
			},
		})
	}

	// 分割线 + 审批结果
	elements = append(elements, map[string]interface{}{"tag": "hr"})
	elements = append(elements, map[string]interface{}{
		"tag": "div",
		"text": map[string]interface{}{
			"tag":     "lark_md",
			"content": resultLabel,
		},
	})

	// 操作人信息
	if operatorInfo != "" {
		elements = append(elements, map[string]interface{}{
			"tag": "div",
			"text": map[string]interface{}{
				"tag":     "lark_md",
				"content": operatorInfo,
			},
		})
	}

	// 注意：不包含 action 元素，按钮已移除防止重复点击

	return map[string]interface{}{
		"config": map[string]interface{}{
			"wide_screen_mode": true,
		},
		"header": map[string]interface{}{
			"template": headerTemplate,
			"title": map[string]interface{}{
				"tag":     "plain_text",
				"content": resultLabel,
			},
		},
		"elements": elements,
	}
}

// ==========================================
// 危险命令检测
// ==========================================

// 默认高危命令正则模式
var defaultDangerousPatterns = []*regexp.Regexp{
	regexp.MustCompile(`\brm\s+`), // 所有 rm 命令（含/不含 flag）
	regexp.MustCompile(`sudo\s+`),
	regexp.MustCompile(`(?i)drop\s+`), // drop/DROP 数据库/表
	regexp.MustCompile(`>\s*.*\.(go|py|js|ts)`),
	regexp.MustCompile(`chmod\s+777`),
	regexp.MustCompile(`mkfs\.`),
	regexp.MustCompile(`dd\s+if=`),
	regexp.MustCompile(`:\(\)\s*\{`), // fork bomb
}

// IsDangerousCommand 检测命令是否匹配高危模式
func IsDangerousCommand(toolName string, argsStr string) bool {
	switch toolName {
	case "bash":
		for _, pattern := range defaultDangerousPatterns {
			if pattern.MatchString(argsStr) {
				return true
			}
		}
	case "write_file", "edit_file":
		return true
	}
	return false
}

// IsDangerousCommandWithPatterns 使用自定义模式检测危险命令
func IsDangerousCommandWithPatterns(toolName string, argsStr string, patterns []*regexp.Regexp) bool {
	switch toolName {
	case "bash":
		for _, pattern := range patterns {
			if pattern.MatchString(argsStr) {
				return true
			}
		}
	case "write_file", "edit_file":
		return true
	}
	return false
}
