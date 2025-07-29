# LRC_Wallpaper

## 对于桌面歌词壁纸修复的软件
Wallpaper订阅链接：https://steamcommunity.com/sharedfiles/filedetails/?id=1551961057

## 运行前提
音乐软件遵守GSMTC协议 （大部分微软商店下载的软件都支持）

因为此软件通过此api接口获取播放信息 所以软件必须遵守此协议才能使用（网易云音乐桌面非UWP版本就不支持）

推荐使用[Spotify](https://www.spotify.com/sg-zh/download/windows/)  免费好用 全平台互通 缺点是注册麻烦了些

## 如何运行
从Releases里下载exe 直接运行（Only Windows10 64bit及以上）

或者以源码

```cmd
python LRC_Wallpaper.py
```

## 关于一些问题
1. Q：歌词显示慢/快几秒
A：正常 过几秒又会自动同步时间
2. Q：开启软件后怎么关闭
A：任务管理器里找到LRC_wallpaper.exe 关闭
4. Q：歌词显示不对
A：可能是歌词获取不到一模一样的获取成其他版本了
5. Q：没法用
A：wallpaper里把壁纸的 启用显示歌曲信息 打开/软件没遵守GSMTC导致无法获取播放信息
