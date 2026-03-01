# Email Agent Heartbeat

检查收件箱是否有未读的重要邮件（真人发来的，非系统通知/广告/验证码）。

- 如果有重要未读邮件：在 Slack 发送摘要通知
- 如果没有：回复 HEARTBEAT_OK
- 深夜（23:00-08:00）除非紧急，否则回复 HEARTBEAT_OK
