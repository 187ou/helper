/**
 * 统一反馈收集组件
 *
 * 在任务完成、AI 生成内容、模板执行等场景收集用户反馈
 * 反馈数据用于演化引擎的偏好学习
 *
 * 使用方式：
 * <FeedbackCollector
 *   context={{ task_id: 123, task_type: 'work' }}
 *   onFeedback={(type) => console.log(type)}
 * />
 */

import { useState } from 'react'
import { Button, Space, Tooltip, message, Popover } from 'antd'
import {
  LikeOutlined, DislikeOutlined, EditOutlined,
} from '@ant-design/icons'
import { api } from '../api'

interface FeedbackCollectorProps {
  context: {
    task_id?: number
    task_type?: string
    original?: string      // 原始内容（用于修改分析）
    modified?: string      // 修改后内容
  }
  onFeedback?: (type: string) => void
  size?: 'small' | 'middle'
  showLabel?: boolean
}

export default function FeedbackCollector({
  context,
  onFeedback,
  size = 'small',
  showLabel = false,
}: FeedbackCollectorProps) {
  const [visible, setVisible] = useState(false)
  const [submitted, setSubmitted] = useState(false)

  async function handleFeedback(type: string) {
    try {
      // 记录反馈到后端
      await api.logBehavior(`feedback_${type}`, {
        task_id: context.task_id,
        task_type: context.task_type,
      })

      // 如果有原始内容和分析，记录到反馈学习
      if (context.original && context.modified && type === 'modify') {
        await fetch('/api/behavior/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_type: 'user_modify',
            event_data: {
              task_id: context.task_id,
              original: context.original,
              modified: context.modified,
            },
          }),
        }).catch(() => {})
      }

      setSubmitted(true)
      message.success(type === 'praise' ? '感谢反馈！系统会记住您的偏好' : '已记录，将优化后续输出')
      onFeedback?.(type)
      setTimeout(() => setVisible(false), 500)
    } catch {
      // 静默处理
    }
  }

  const feedbackButtons = (
    <Space direction="vertical" size="small">
      <Space>
        <Tooltip title="满意（正反馈）">
          <Button
            type="text"
            icon={<LikeOutlined style={{ color: '#52c41a' }} />}
            size={size}
            onClick={() => handleFeedback('praise')}
          >
            {showLabel && '满意'}
          </Button>
        </Tooltip>
        <Tooltip title="需要修改">
          <Button
            type="text"
            icon={<EditOutlined style={{ color: '#faad14' }} />}
            size={size}
            onClick={() => handleFeedback('modify')}
          >
            {showLabel && '需修改'}
          </Button>
        </Tooltip>
        <Tooltip title="完全不对，重做">
          <Button
            type="text"
            icon={<DislikeOutlined style={{ color: '#ff4d4f' }} />}
            size={size}
            onClick={() => handleFeedback('reject')}
          >
            {showLabel && '重做'}
          </Button>
        </Tooltip>
      </Space>
    </Space>
  )

  if (submitted) {
    return (
      <span className="text-xs text-green-500">✓ 已反馈</span>
    )
  }

  return (
    <Popover
      content={feedbackButtons}
      title={<span className="text-xs">这个结果如何？</span>}
      trigger="click"
      open={visible}
      onOpenChange={setVisible}
    >
      <Button type="text" size={size} icon={<LikeOutlined />}>
        {showLabel && '反馈'}
      </Button>
    </Popover>
  )
}
