import asyncio
import time
from winsdk.windows.media.control import (
    GlobalSystemMediaTransportControlsSessionManager,
    GlobalSystemMediaTransportControlsSessionPlaybackStatus
)
from flask import Flask, jsonify
from threading import Thread
import requests
import re

import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LRCParser:
    def __init__(self, lrc_text):
        self.lines = []
        self.parse(lrc_text)
    
    def parse(self, lrc_text):
        pattern = r'\[(\d+):(\d+)\.(\d+)\](.*)'
        for line in lrc_text.split('\n'):
            matches = re.findall(pattern, line)
            if matches:
                for min, sec, ms, text in matches:
                    time_sec = int(min) * 60 + int(sec) + int(ms) / 1000
                    self.lines.append((time_sec, text.strip()))
        self.lines.sort(key=lambda x: x[0])
    
    def get_lyric_at_time(self, current_time):
        current_lyric = ""
        for time_sec, text in self.lines:
            if time_sec <= current_time:
                current_lyric = text
            else:
                break
        return current_lyric

class MediaPlayerMonitor:
    def __init__(self):
        self.last_playback_status = None
        self.last_sync_time = 0
        self.current_position = 0
        self.last_update_time = 0
        self.is_playing = False
        self.current_song_id = None
        self.last_Title = None
        self.timer_offset = 0
        self.duration = 0
        self.lrc_parser = None
        self.trans_parser = None
        self.current_song_info = None
        self.data = {
            "AppName": "网易云音乐",
            "Title": "",
            "AllTime": "",
            "Now": "",
            "ChineseLryic": "",
            "Lryic": "",
            "FormattedTime": "",
        }
        
    async def update_playback_state(self):
        try:
            manager = await GlobalSystemMediaTransportControlsSessionManager.request_async()
            session = manager.get_current_session()
            
            if session is None:
                self.is_playing = False
                self.last_playback_status = None
                return None
            
            props = await session.try_get_media_properties_async()
            playback_info = session.get_playback_info()
            timeline = session.get_timeline_properties()
            
            # 更新歌曲时长
            self.duration = timeline.end_time.total_seconds()

            # 获取当前播放状态
            current_status = playback_info.playback_status
            self.is_playing = (current_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING)

            # 歌曲切换检测
            song_id = f"{props.title}-{props.artist}"
            if song_id != self.current_song_id:
                self.current_song_id = song_id
                self.timer_offset = timeline.position.total_seconds()
                self.last_update_time = time.time()
                self.current_position = 0
                self.last_sync_time = self.last_update_time
                self.last_Title = f"{props.title} - {props.artist}"
                await self.update_lyrics(props.title, props.artist)
                logger.info(f"Song changed: {song_id}")
                
            # 播放恢复时，重设计时基准
            if self.last_playback_status is not None and self.last_playback_status != current_status:
                if current_status == GlobalSystemMediaTransportControlsSessionPlaybackStatus.PLAYING:
                    self.timer_offset = timeline.position.total_seconds()
                    self.last_update_time = time.time()
                    self.last_sync_time = self.last_update_time
                    logger.info("Playback resumed, timer offset reset to current position")

            # 每隔5秒自动校准时间
            if self.is_playing:
                now = time.time()
                if now - getattr(self, 'last_sync_time', 0) >= 5:
                    self.timer_offset = timeline.position.total_seconds()
                    self.last_update_time = now
                    self.last_sync_time = now
                    logger.info("Periodic time sync with player timeline")

            # 更新状态记录
            self.last_playback_status = current_status

            self.current_song_info = {
                "title": props.title if props.title else "未知标题",
                "artist": props.artist if props.artist else "未知艺术家",
                "duration": self.duration
            }

            return self.current_song_info

        except Exception as e:
            logger.error(f"Error updating playback state: {e}")
            return None


    async def update_lyrics(self, title, artist):
        try:
            music_id = self.get_music_id(title, artist)
            if music_id:
                print(music_id)
                lyrics = self.get_lrc(music_id)
                if lyrics:
                    self.lrc_parser = LRCParser(lyrics["lrc"])
                    self.trans_parser = LRCParser(lyrics["trans"]) if lyrics["trans"] else None
        except Exception as e:
            logger.error(f"Error updating lyrics: {e}")

    def get_current_time(self):
        if not self.is_playing:
            return self.current_position

        now = time.time()
        elapsed = now - self.last_update_time
        estimated = self.timer_offset + elapsed

        if self.current_song_id:
            self.current_position = max(self.current_position, estimated)
        else:
            self.current_position = estimated

        self.current_position = min(self.current_position, self.duration)
        return self.current_position

    def get_music_id(self, name: str, artist: str = ""):
        try:
            query = f"{name} {artist}".strip()
            api_url = f"https://music.163.com/api/search/get/web?csrf_token=hlpretag=&hlposttag=&s={query}&type=1&offset=0&total=true&limit=10"
            resp = requests.get(api_url)
            if resp.status_code == 200:
                songs = resp.json()["result"]["songs"]
                if songs:
                    return songs[0]["id"]
        except Exception as e:
            logger.error(f"Error getting music ID: {e}")
        return None

    def get_lrc(self, id: int):
        try:
            api_url = f"https://api.vkeys.cn/v2/music/netease/lyric?id={id}"
            resp = requests.get(api_url)
            if resp.status_code == 200:
                resp_data = resp.json()
                return {
                    "lrc": resp_data["data"]["lrc"],
                    "trans": resp_data["data"].get("trans", ""),
                    "roma": resp_data["data"].get("roma", "")
                }
        except Exception as e:
            logger.error(f"Error getting lyrics: {e}")
        return None

    def format_time(self, seconds):
        minutes, seconds = divmod(int(seconds), 60)
        return f"{minutes:02d}:{seconds:02d}"

    def get_current_data(self):
        if not self.current_song_info:
            return self.data
        
        current_time = self.get_current_time()
        current_lyric = self.lrc_parser.get_lyric_at_time(current_time) if self.lrc_parser else ""
        current_trans = self.trans_parser.get_lyric_at_time(current_time) if self.trans_parser else ""
        
        self.data["Title"] = f"{self.current_song_info['title']} - {self.current_song_info['artist']}"
        self.data["AllTime"] = int(self.duration)
        self.data["Now"] = int(current_time)
        self.data["Lryic"] = current_lyric
        self.data["ChineseLryic"] = current_trans
        self.data["FormattedTime"] = f"({self.format_time(current_time)}/{self.format_time(self.duration)})"
        
        return self.data

async def monitor_loop(monitor):
    while True:
        try:
            await monitor.update_playback_state()
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Error in monitor loop: {e}")
            await asyncio.sleep(5)


app = Flask(__name__)
monitor = MediaPlayerMonitor()

@app.route("/BGMName/")
def get_bgm_info():
    data = monitor.get_current_data()
    print(data)
    return jsonify(data)

def run_flask():
    app.run(port=62333, debug=False)

def run_asyncio_loop():
    asyncio.run(monitor_loop(monitor))

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    
    run_asyncio_loop()