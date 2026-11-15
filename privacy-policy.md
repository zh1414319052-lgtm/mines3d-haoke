# Privacy / 隐私说明

The Haoke edition of Mines3D has offline and online modes. Solo boards, settings and progress stay in the app's local storage. Android's system backup may include app data according to device settings. No advertising or analytics SDK is added.

Online play contacts https://cleanbizai.com for account sign-in, profile, rooms, match commands, results and reconnects. The server necessarily processes the account information and game actions needed for these services. The native client does not retain your password; it keeps an authentication token protected with Android Keystore. Website account/privacy policies also apply when using the platform. Ordinary network metadata, including IP addresses, is visible to the service.

The stable edition checks signed version metadata at https://www.haoke.org only from the settled foreground menu or a manual Settings check. The request identifies the app and stable channel through the URL; it does not send your account, saved board or device ID. Update preferences and rollback protection are stored locally. Automatic checks fail quietly and have bounded foreground retries. Version-page links open only after you tap them. There is no background polling or automatic installation.

浩科版包含离线与联网玩法。单机棋盘、设置与进度保存在应用本地；系统备份可能按手机设置包含应用数据。未新增广告或统计 SDK。

联机功能通过 cleanbizai.com 处理登录、游戏资料、房间、操作、结算与重连所需数据。客户端不保存密码，登录令牌使用 Android Keystore 保护。平台账号功能还适用网站的账号与隐私规则；服务器可见 IP 等普通连接信息。

正式版仅在首页前台或手动检查时访问 haoke.org 的签名版本接口。请求 URL 标明应用与正式通道，不上传账号、存档棋盘或设备标识。更新偏好与防回滚记录保存在本地。失败静默处理并有限重试；点击后才打开版本网页，不进行后台轮询或自动安装。
