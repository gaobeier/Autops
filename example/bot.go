package feishu

import (
	"bytes"
	"context"
	"encoding/base64"
	"encoding/json"
	"io"
	"log"
	"net/http"
	"path/filepath"
	"strings"
	"sync"
	"time"

	lark "github.com/larksuite/oapi-sdk-go/v3"
	larkcore "github.com/larksuite/oapi-sdk-go/v3/core"
	"github.com/larksuite/oapi-sdk-go/v3/event/dispatcher"
	"github.com/larksuite/oapi-sdk-go/v3/event/dispatcher/callback"
	larkim "github.com/larksuite/oapi-sdk-go/v3/service/im/v1"
	larkws "github.com/larksuite/oapi-sdk-go/v3/ws"

	"github.com/Gordon/OpsClaw/internal/engine"
	"github.com/Gordon/OpsClaw/internal/schema"
)

// updateCardMessage 通过 Message Patch API 更新已发送的卡片消息
func (b *FeishuBot) updateCardMessage(messageID string, cardJSON string) {
	if b.client == nil || messageID == "" {
		log.Printf("[FeishuBot] 无法更新卡片: client=%v, messageID=%q\n", b.client != nil, messageID)
		return
	}

	// 延迟 500ms 确保回调响应已返回，避免与飞书服务端冲突
	time.Sleep(500 * time.Millisecond)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	log.Printf("[FeishuBot] 更新卡片消息: messageID=%s\n", messageID)

	req := larkim.NewPatchMessageReqBuilder().
		MessageId(messageID).
		Body(&larkim.PatchMessageReqBody{
			Content: larkcore.StringPtr(cardJSON),
		}).
		Build()

	resp, err := b.client.Im.V1.Message.Patch(ctx, req)
	if err != nil {
		log.Printf("[FeishuBot] 更新卡片消息失败: %v\n", err)
		return
	}
	if !resp.Success() {
		log.Printf("[FeishuBot] 更新卡片消息失败: code=%d, msg=%s\n", resp.Code, resp.Msg)
		return
	}
	log.Printf("[FeishuBot] 卡片消息更新成功: messageID=%s\n", messageID)
}

// EngineFactory 创建引擎实例的工厂函数
// 每个 session 需要独立的引擎实例（绑定独立的 CostTracker）
type EngineFactory func(session *engine.Session) *engine.AgentEngine

// FeishuBot 飞书 Bot 封装
type FeishuBot struct {
	client        *lark.Client
	wsClient      *larkws.Client
	engineFactory EngineFactory
	workDir       string
	appID         string
	appSecret     string
	botOpenID     string
	botOnce       sync.Once

	// tenant_access_token 缓存（有效期 2 小时，提前 5 分钟刷新）
	tenantToken string
	tokenExpiry time.Time
	tokenMu     sync.Mutex
}

// NewFeishuBot 创建飞书 Bot 实例
func NewFeishuBot(appID string, appSecret string, factory EngineFactory, workDir string) *FeishuBot {
	client := lark.NewClient(appID, appSecret,
		lark.WithLogLevel(larkcore.LogLevelInfo),
	)

	bot := &FeishuBot{
		client:        client,
		engineFactory: factory,
		workDir:       workDir,
		appID:         appID,
		appSecret:     appSecret,
	}

	// 创建事件分发器并注册消息接收处理
	eventHandler := bot.buildEventHandler()

	wsClient := larkws.NewClient(appID, appSecret,
		larkws.WithEventHandler(eventHandler),
		larkws.WithLogLevel(larkcore.LogLevelInfo),
	)
	bot.wsClient = wsClient

	return bot
}

// buildEventHandler 构建事件处理器
func (b *FeishuBot) buildEventHandler() *dispatcher.EventDispatcher {
	return dispatcher.NewEventDispatcher("", "").
		OnP2MessageReceiveV1(func(ctx context.Context, event *larkim.P2MessageReceiveV1) error {
			b.onMessageReceive(ctx, event)
			return nil
		}).
		OnP2CardActionTrigger(func(ctx context.Context, event *callback.CardActionTriggerEvent) (*callback.CardActionTriggerResponse, error) {
			return b.onCardAction(ctx, event)
		})
}

// onCardAction 处理卡片按钮回调（审批）
func (b *FeishuBot) onCardAction(ctx context.Context, event *callback.CardActionTriggerEvent) (*callback.CardActionTriggerResponse, error) {
	if event == nil || event.Event == nil || event.Event.Action == nil {
		log.Printf("[FeishuBot] 无效的卡片回调事件\n")
		return nil, nil
	}

	action := event.Event.Action
	actionValue := action.Value

	taskID, _ := actionValue["task_id"].(string)
	actionType, _ := actionValue["action"].(string)

	if taskID == "" || actionType == "" {
		log.Printf("[FeishuBot] 无效的卡片回调: %v\n", actionValue)
		return nil, nil
	}

	log.Printf("[FeishuBot] 审批回调: taskID=%s, action=%s\n", taskID, actionType)

	var allowed bool
	var reason string
	var toastMsg string
	var resultLabel string
	var headerTemplate string

	switch actionType {
	case "approve_once":
		allowed = true
		reason = "用户批准（允许一次）"
		toastMsg = "✅ 已批准（本次执行）"
		resultLabel = "✅ 审批通过（允许一次）"
		headerTemplate = "green"
	case "approve_session":
		allowed = true
		reason = "用户批准（本次会话）"
		toastMsg = "✅ 已批准（本次会话内不再询问）"
		resultLabel = "✅ 审批通过（本次会话）"
		headerTemplate = "green"
	case "approve_always":
		allowed = true
		reason = "用户批准（始终允许）"
		toastMsg = "✅ 已批准（始终允许此命令）"
		resultLabel = "✅ 审批通过（始终允许）"
		headerTemplate = "green"
	case "reject":
		allowed = false
		reason = "用户拒绝"
		toastMsg = "❌ 已拒绝"
		resultLabel = "❌ 已拒绝"
		headerTemplate = "red"
	default:
		log.Printf("[FeishuBot] 未知的审批操作: %s\n", actionType)
		return nil, nil
	}

	// 获取原始审批详情（工具名、参数），用于结果卡片回显
	detail := GlobalApprovalMgr.GetAndRemoveApprovalDetail(taskID)

	// 解析审批结果
	GlobalApprovalMgr.ResolveApproval(taskID, allowed, reason)

	// 获取操作人信息
	operatorName := ""
	if event.Event.Operator != nil {
		operatorName = event.Event.Operator.OpenID
	}

	// 构建更新后的卡片（更新 header 颜色 + 显示结果 + 移除按钮）
	updatedCard := buildApprovalResultCard(taskID, detail, resultLabel, headerTemplate, operatorName)

	// 通过 Message API 更新原卡片（避免 SDK 回调响应的 Card 包装格式问题）
	messageID := ""
	if event.Event.Context != nil {
		messageID = event.Event.Context.OpenMessageID
	}
	if messageID != "" {
		cardJSON, _ := json.Marshal(updatedCard)
		go b.updateCardMessage(messageID, string(cardJSON))
	}

	// 回调仅返回 Toast 提示
	return &callback.CardActionTriggerResponse{
		Toast: &callback.Toast{
			Type:    "info",
			Content: toastMsg,
		},
	}, nil
}

// Start 启动长连接，阻塞运行
func (b *FeishuBot) Start(ctx context.Context) error {
	log.Println("[FeishuBot] 启动 WebSocket 长连接...")
	return b.wsClient.Start(ctx)
}

// onMessageReceive 处理接收到的消息事件
func (b *FeishuBot) onMessageReceive(ctx context.Context, event *larkim.P2MessageReceiveV1) {
	if event.Event == nil || event.Event.Message == nil {
		return
	}

	msg := event.Event.Message
	sender := event.Event.Sender

	messageID := derefStr(msg.MessageId)
	chatID := derefStr(msg.ChatId)
	chatType := derefStr(msg.ChatType)
	messageType := derefStr(msg.MessageType)

	// 获取发送者 ID
	var userID string
	if sender != nil && sender.SenderId != nil {
		userID = derefStr(sender.SenderId.OpenId)
	}

	log.Printf("[FeishuBot] 收到消息: chatID=%s, chatType=%s, msgType=%s, userID=%s\n",
		chatID, chatType, messageType, userID)

	// 群聊场景：只在被 @提及时才响应
	if chatType == "group" {
		botID := b.getBotOpenID()
		mentioned := false
		for _, m := range msg.Mentions {
			if m == nil || m.Id == nil {
				continue
			}
			openID := derefStr(m.Id.OpenId)
			if botID != "" && openID == botID {
				mentioned = true
				break
			}
		}
		if !mentioned {
			log.Printf("[FeishuBot] 群聊消息未 @机器人，忽略: chatID=%s\n", chatID)
			return
		}
	}

	// 处理文本、富文本(post)、纯图片(image) 消息
	var content string
	var images []schema.ImageData

	switch messageType {
	case "text":
		content = parseTextContent(derefStr(msg.Content))
	case "post":
		content, images = b.parsePostContent(messageID, derefStr(msg.Content))
	case "image":
		// 纯图片消息，Content 格式为 {"image_key":"img_xxx"}
		imgKey := parseImageKey(derefStr(msg.Content))
		if imgKey != "" {
			if img := b.downloadImage(messageID, imgKey); img != nil {
				images = []schema.ImageData{*img}
			}
		}
		content = ""
	default:
		log.Printf("[FeishuBot] 忽略不支持的消息类型 (type=%s)\n", messageType)
		return
	}

	// 既无文本也无图片，跳过
	if content == "" && len(images) == 0 {
		log.Printf("[FeishuBot] 消息内容为空，跳\n")
		return
	}

	log.Printf("[FeishuBot] 消息内容: %s (图片数: %d)\n", truncate(content, 100), len(images))

	// 在新 goroutine 中处理（避免阻塞事件循环）
	// 注意：不传递事件回调的 ctx，因为它在回调返回后即失效
	go b.handleMessage(chatID, messageID, content, images, userID)
}

// handleMessage 处理消息并运行引擎
func (b *FeishuBot) handleMessage(chatID string, messageID string, content string, images []schema.ImageData, userID string) {
	// 创建独立的 context（事件回调的 ctx 在 goroutine 启动前可能已过期）
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Minute)
	defer cancel()

	// 1. 获取或创建 Session
	sessionID := chatID + "_" + userID
	session := engine.GlobalSessionMgr.GetOrCreate(sessionID, b.workDir)

	// 2. 追加用户消息（含图片）
	userMsg := schema.Message{
		Role:    schema.RoleUser,
		Content: content,
	}
	if len(images) > 0 {
		userMsg.Images = images
		// 无文本时补一句占位提示，避免 Content 为空导致部分模型报错
		if content == "" {
			userMsg.Content = "（用户发送了一张图片）"
		}
	}
	session.Append(userMsg)

	// 3. 创建引擎实例
	eng := b.engineFactory(session)

	// 4. 创建 Reporter
	reporter := NewFeishuReporter(b.client, chatID, messageID)

	// 5. 注入 Reporter 到 context（供审批中间件使用）
	msgCtx := ContextWithReporter(ctx, reporter)

	// 6. 运行引擎
	if err := eng.Run(msgCtx, session, reporter); err != nil {
		log.Printf("[FeishuBot] 引擎运行出错: %v\n", err)
		reporter.SendText(msgCtx, "❌ 引擎运行出错: "+err.Error())
	}
}

// parseTextContent 解析飞书文本消息内容
// 飞书文本消息的 Content 格式为: {"text":"实际内容"}
func parseTextContent(contentJSON string) string {
	var data struct {
		Text string `json:"text"`
	}
	if err := json.Unmarshal([]byte(contentJSON), &data); err != nil {
		return contentJSON // 解析失败则返回原始内容
	}
	return data.Text
}

// parseImageKey 解析纯图片消息的 image_key
// 飞书图片消息的 Content 格式为: {"image_key":"img_xxx"}
func parseImageKey(contentJSON string) string {
	var data struct {
		ImageKey string `json:"image_key"`
	}
	if err := json.Unmarshal([]byte(contentJSON), &data); err != nil {
		return ""
	}
	return data.ImageKey
}

// parsePostContent 解析飞书富文本消息，提取文本和图片
// 飞书 post 消息的 Content 格式为:
//
//	{"zh_cn":{"title":"标题","content":[[{"tag":"text","text":".."},{"tag":"img","image_key":"img_xxx"}]]}}
//
// 可能存在多语言键（zh_cn/en_us 等），取第一个有效的
func (b *FeishuBot) parsePostContent(messageID string, contentJSON string) (string, []schema.ImageData) {
	// 飞书 WebSocket 推送的 post 消息 Content 直接是平铺结构：
	// {"title":"","content":[[{"tag":"img","image_key":"...","width":500,"height":500}],[{"tag":"text","text":"...","style":[]}]]}
	var post struct {
		Title   string              `json:"title"`
		Content [][]json.RawMessage `json:"content"`
	}
	if err := json.Unmarshal([]byte(contentJSON), &post); err != nil {
		log.Printf("[FeishuBot] post JSON 解析失败: %v, raw: %s\n", err, truncate(contentJSON, 500))
		return "", nil
	}

	var textParts []string
	var images []schema.ImageData

	if post.Title != "" {
		textParts = append(textParts, post.Title)
	}

	for _, paragraph := range post.Content {
		for _, node := range paragraph {
			var elem struct {
				Tag      string `json:"tag"`
				Text     string `json:"text"`
				ImageKey string `json:"image_key"`
			}
			if err := json.Unmarshal(node, &elem); err != nil {
				continue
			}
			switch elem.Tag {
			case "text":
				if elem.Text != "" {
					textParts = append(textParts, elem.Text)
				}
			case "img":
				if elem.ImageKey != "" {
					if img := b.downloadImage(messageID, elem.ImageKey); img != nil {
						images = append(images, *img)
					}
				}
			}
		}
	}

	var sb strings.Builder
	for i, p := range textParts {
		if i > 0 {
			sb.WriteString("\n")
		}
		sb.WriteString(p)
	}
	return sb.String(), images
}

// getTenantAccessToken 获取飞书 tenant_access_token（带缓存，提前 5 分钟刷新）
func (b *FeishuBot) getTenantAccessToken() string {
	b.tokenMu.Lock()
	defer b.tokenMu.Unlock()

	// token 还有 5 分钟以上有效期，直接返回缓存
	if b.tenantToken != "" && time.Now().Before(b.tokenExpiry.Add(-5*time.Minute)) {
		return b.tenantToken
	}

	// 重新获取 token
	tokenReq := map[string]string{
		"app_id":     b.appID,
		"app_secret": b.appSecret,
	}
	body, _ := json.Marshal(tokenReq)
	resp, err := http.Post(
		"https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
		"application/json", bytes.NewReader(body),
	)
	if err != nil {
		log.Printf("[FeishuBot] 获取 tenant_access_token 失败: %v\n", err)
		return ""
	}
	defer resp.Body.Close()

	var tokenResp struct {
		Code              int    `json:"code"`
		Msg               string `json:"msg"`
		TenantAccessToken string `json:"tenant_access_token"`
		Expire            int    `json:"expire"` // 有效期（秒）
	}
	json.NewDecoder(resp.Body).Decode(&tokenResp)
	if tokenResp.TenantAccessToken == "" {
		log.Printf("[FeishuBot] tenant_access_token 为空, code=%d, msg=%s\n", tokenResp.Code, tokenResp.Msg)
		return ""
	}

	b.tenantToken = tokenResp.TenantAccessToken
	expire := time.Duration(tokenResp.Expire) * time.Second
	if expire <= 0 {
		expire = 2 * time.Hour // 默认 2 小时
	}
	b.tokenExpiry = time.Now().Add(expire)
	log.Printf("[FeishuBot] tenant_access_token 已刷新，有效期 %v\n", expire)

	return b.tenantToken
}

// downloadImage 下载用户发送的图片，返回 base64 编码的 ImageData
// 用户发送的图片必须使用"获取消息中的资源文件"接口，而非 images/{image_key} 接口
// API: GET /open-apis/im/v1/messages/{message_id}/resources/{file_key}?type=image
func (b *FeishuBot) downloadImage(messageID string, fileKey string) *schema.ImageData {
	if b.client == nil {
		log.Printf("[FeishuBot] 下载图片失败：无 lark client\n")
		return nil
	}

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()

	req := larkim.NewGetMessageResourceReqBuilder().
		MessageId(messageID).
		FileKey(fileKey).
		Type("image").
		Build()

	resp, err := b.client.Im.V1.MessageResource.Get(ctx, req)
	if err != nil {
		log.Printf("[FeishuBot] 下载图片失败 (key=%s): %v\n", fileKey, err)
		return nil
	}
	if !resp.Success() {
		log.Printf("[FeishuBot] 下载图片失败 (key=%s): code=%d, msg=%s\n",
			fileKey, resp.Code, resp.Msg)
		return nil
	}

	imgBytes, err := io.ReadAll(resp.File)
	if err != nil {
		log.Printf("[FeishuBot] 读取图片数据失败 (key=%s): %v\n", fileKey, err)
		return nil
	}

	// 从 Content-Disposition 推断文件扩展名，映射到 MIME 类型
	mimeType := "image/jpeg" // 飞书图片默认 jpeg
	fileName := resp.FileName
	if ext := strings.ToLower(filepath.Ext(fileName)); ext != "" {
		switch ext {
		case ".png":
			mimeType = "image/png"
		case ".gif":
			mimeType = "image/gif"
		case ".webp":
			mimeType = "image/webp"
		case ".bmp":
			mimeType = "image/bmp"
		}
	}

	log.Printf("[FeishuBot] 图片下载成功 (key=%s, size=%d bytes, type=%s)\n",
		fileKey, len(imgBytes), mimeType)

	return &schema.ImageData{
		Base64:   base64.StdEncoding.EncodeToString(imgBytes),
		MIMEType: mimeType,
	}
}

// getBotOpenID 获取机器人自身的 OpenID（懒加载 + 缓存）
func (b *FeishuBot) getBotOpenID() string {
	b.botOnce.Do(func() {
		token := b.getTenantAccessToken()
		if token == "" {
			log.Printf("[FeishuBot] 获取 Bot OpenID 失败：无 tenant_access_token\n")
			return
		}

		// 获取 Bot Info
		req, _ := http.NewRequest("GET", "https://open.feishu.cn/open-apis/bot/v3/info", nil)
		req.Header.Set("Authorization", "Bearer "+token)
		botResp, err := http.DefaultClient.Do(req)
		if err != nil {
			log.Printf("[FeishuBot] 获取 Bot Info 失败: %v\n", err)
			return
		}
		defer botResp.Body.Close()

		var botInfo struct {
			Bot struct {
				OpenID string `json:"open_id"`
			} `json:"bot"`
		}
		json.NewDecoder(botResp.Body).Decode(&botInfo)
		b.botOpenID = botInfo.Bot.OpenID

		if b.botOpenID != "" {
			log.Printf("[FeishuBot] Bot OpenID: %s\n", b.botOpenID)
		} else {
			log.Printf("[FeishuBot] 未能获取 Bot OpenID，群聊 @检测可能不生效\n")
		}
	})
	return b.botOpenID
}

// derefStr 安全地取指针字符串值
func derefStr(s *string) string {
	if s == nil {
		return ""
	}
	return *s
}
