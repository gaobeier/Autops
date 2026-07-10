package feishu

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	larkcore "github.com/larksuite/oapi-sdk-go/v3/core"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"

	"github.com/Gordon/OpsClaw/internal/schema"
)

// FeishuReporter 飞书消息输出实现
type FeishuReporter struct {
	client    *lark.Client
	chatID    string
	replyID   string // 回复的消息 ID
	streamBuf strings.Builder // 累积流式内容
}

// NewFeishuReporter 创建飞书 Reporter
func NewFeishuReporter(client *lark.Client, chatID string, replyID string) *FeishuReporter {
	return &FeishuReporter{
		client:  client,
		chatID:  chatID,
		replyID: replyID,
	}
}

func (r *FeishuReporter) OnThinking(ctx context.Context) {
	r.SendText(ctx, "💭 思考中...")
}

func (r *FeishuReporter) OnToolCall(ctx context.Context, toolName string, args string) {
	display := args
	if len(display) > 200 {
		display = display[:200] + "..."
	}
	r.SendText(ctx, fmt.Sprintf("🔧 调用工具: %s\n参数: %s", toolName, display))
}

func (r *FeishuReporter) OnToolResult(ctx context.Context, toolName string, result string, isError bool) {
	display := result
	if len(display) > 500 {
		display = display[:500] + "\n... (已截断)"
	}

	prefix := "✅"
	if isError {
		prefix = "❌"
	}
	r.SendText(ctx, fmt.Sprintf("%s %s 执行结果:\n%s", prefix, toolName, display))
}

func (r *FeishuReporter) OnMessage(ctx context.Context, content string) {
	// 流式模式：引擎传空字符串表示流式结束，发送累积内容
	// 非流式模式：content 包含完整回复，直接发送
	if content == "" {
		if r.streamBuf.Len() > 0 {
			r.SendText(ctx, r.streamBuf.String())
			r.streamBuf.Reset()
		}
		return
	}
	r.SendText(ctx, content)
}

// OnContentDelta 飞书不支持实时流式，将增量累积到缓冲区
func (r *FeishuReporter) OnContentDelta(ctx context.Context, delta string) {
	r.streamBuf.WriteString(delta)
}

// SendText 发送文本消息到飞书（回复原始消息）
func (r *FeishuReporter) SendText(ctx context.Context, text string) {
	if r.client == nil {
		log.Printf("[Feishu] 无 client，打印到日志: %s\n", truncate(text, 200))
		return
	}

	// 构建文本消息内容
	content, _ := json.Marshal(map[string]string{"text": text})
	contentStr := string(content)

	// 使用 Reply API 回复消息
	if r.replyID != "" {
		req := larkim.NewReplyMessageReqBuilder().
			MessageId(r.replyID).
			Body(&larkim.ReplyMessageReqBody{
				Content: larkcore.StringPtr(contentStr),
				MsgType: larkcore.StringPtr("text"),
			}).
			Build()

		resp, err := r.client.Im.V1.Message.Reply(ctx, req)
		if err != nil {
			log.Printf("[Feishu] 回复消息失败: %v\n", err)
			return
		}
		if !resp.Success() {
			log.Printf("[Feishu] 回复消息失败: code=%d, msg=%s\n", resp.Code, resp.Msg)
		}
		return
	}

	// 无 replyID，使用 Create API 发送到 chat
	req := larkim.NewCreateMessageReqBuilder().
		ReceiveIdType("chat_id").
		Body(&larkim.CreateMessageReqBody{
			ReceiveId: larkcore.StringPtr(r.chatID),
			Content:   larkcore.StringPtr(contentStr),
			MsgType:   larkcore.StringPtr("text"),
		}).
		Build()

	resp, err := r.client.Im.V1.Message.Create(ctx, req)
	if err != nil {
		log.Printf("[Feishu] 发送消息失败: %v\n", err)
		return
	}
	if !resp.Success() {
		log.Printf("[Feishu] 发送消息失败: code=%d, msg=%s\n", resp.Code, resp.Msg)
	}
}

// SendCard 发送交互式卡片消息到飞书（回复原始消息）
func (r *FeishuReporter) SendCard(ctx context.Context, cardJSON string) {
	if r.client == nil {
		log.Printf("[Feishu] 无 client，跳过发送卡片\n")
		return
	}

	if r.replyID != "" {
		req := larkim.NewReplyMessageReqBuilder().
			MessageId(r.replyID).
			Body(&larkim.ReplyMessageReqBody{
				Content: larkcore.StringPtr(cardJSON),
				MsgType: larkcore.StringPtr("interactive"),
			}).
			Build()

		resp, err := r.client.Im.V1.Message.Reply(ctx, req)
		if err != nil {
			log.Printf("[Feishu] 回复卡片消息失败: %v\n", err)
			return
		}
		if !resp.Success() {
			log.Printf("[Feishu] 回复卡片消息失败: code=%d, msg=%s\n", resp.Code, resp.Msg)
		}
		return
	}

	req := larkim.NewCreateMessageReqBuilder().
		ReceiveIdType("chat_id").
		Body(&larkim.CreateMessageReqBody{
			ReceiveId: larkcore.StringPtr(r.chatID),
			Content:   larkcore.StringPtr(cardJSON),
			MsgType:   larkcore.StringPtr("interactive"),
		}).
		Build()

	resp, err := r.client.Im.V1.Message.Create(ctx, req)
	if err != nil {
		log.Printf("[Feishu] 发送卡片消息失败: %v\n", err)
		return
	}
	if !resp.Success() {
		log.Printf("[Feishu] 发送卡片消息失败: code=%d, msg=%s\n", resp.Code, resp.Msg)
	}
}

// SendApprovalCard 发送审批卡片
func (r *FeishuReporter) SendApprovalCard(ctx context.Context, toolCall schema.ToolCall, argsStr string) {
	cardJSON := buildApprovalCardJSON(toolCall, argsStr)
	r.SendCard(ctx, cardJSON)
}

// ==========================================
// Context 传播：将 Reporter 注入到 context 中
// ==========================================

type reporterKey struct{}

// ContextWithReporter 将 FeishuReporter 注入到 context
func ContextWithReporter(ctx context.Context, r *FeishuReporter) context.Context {
	return context.WithValue(ctx, reporterKey{}, r)
}

// ReporterFromContext 从 context 中提取 FeishuReporter
func ReporterFromContext(ctx context.Context) *FeishuReporter {
	if r, ok := ctx.Value(reporterKey{}).(*FeishuReporter); ok {
		return r
	}
	return nil
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen] + "..."
}
