# -*- coding: utf-8 -*-

import flet as ft
import os
import sys
import json
import re
import shutil
import winreg
import socket
from pathlib import Path
from datetime import datetime
import threading
import time
import uuid
import tempfile
import atexit
import logging
from logging.handlers import RotatingFileHandler
import subprocess
# # externalディレクトリのパスを取得
# candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external")
# if os.path.isdir(candidate):
#     EXTERNAL_PATH = candidate
# else:
#     if sys.platform.startswith("win"):
#         # LOCALAPPDATA 環境変数が設定されている場合はこちらを利用
#         data_dir = os.getenv('LOCALAPPDATA', os.path.expanduser("~"))
#     elif sys.platform == "darwin":
#         data_dir = os.path.join(os.path.expanduser("~"), "Library", "Application Support")
#     else: # Linux/Unix
#         data_dir = os.getenv('XDG_DATA_HOME', os.path.join(os.path.expanduser("~"), ".local", "share"))
#     EXTERNAL_PATH = os.path.join(data_dir, "YDownloader", "external")
# # external 以下の各ライブラリのパスをリスト化
# external_libs = ["appdirs", "PIL", "requests", "yt_dlp"]
# # 各ディレクトリを sys.path に追加
# for lib in external_libs:
#     lib_path = os.path.join(EXTERNAL_PATH, lib)
#     sys.path.insert(0, lib_path)
# # ここで external/ 内のモジュールが import 可能になる
# # 各ライブラリを import
# from yt_dlp import YoutubeDL
# import requests
# from PIL import Image
# from appdirs import user_data_dir, user_config_dir
try:
    from yt_dlp import YoutubeDL
    import requests
    from PIL import Image
    from appdirs import user_data_dir, user_config_dir
    from concurrent.futures import ThreadPoolExecutor
except ImportError as e:
    raise(f"必要なライブラリのインポートに失敗しました: {e}")


"""
Nuitkaを使用したFletデスクトップアプリのパック → flet build を利用する方法に変更
https://github.com/flet-dev/flet/discussions/1314
Pythonのexe化について
https://zenn.dev/kitagawadisk/articles/aead46336ce3b7
yt-dlpのバージョンアップにexe化後にパッチを当てるなどして対応する予定
"""

def get_download_folder():
    """ダウンロードフォルダーを取得"""
    # Windowsの場合、レジストリから取得
    if sys.platform == "win32":
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders"
            )
            # DownloadsフォルダのGUID: {374DE290-123F-4565-9164-39C4925E467B}
            downloads, _ = winreg.QueryValueEx(key, "{374DE290-123F-4565-9164-39C4925E467B}")
            return downloads
        except Exception:
            # 万が一取得できなかった場合は、ホームディレクトリにDownloadsを結合
            return str(Path.home() / "Downloads")
    
    # macOSの場合
    elif sys.platform == "darwin":
        return str(Path.home() / "Downloads")
    
    # Linuxなどのその他のOSの場合
    else:
        xdg_config = Path.home() / ".config" / "user-dirs.dirs"
        if xdg_config.exists():
            try:
                with open(xdg_config, "r", encoding="utf-8") as f:
                    for line in f:
                        if "XDG_DOWNLOAD_DIR" in line:
                            # 例: XDG_DOWNLOAD_DIR="$HOME/Downloads"
                            parts = line.strip().split("=")
                            if len(parts) == 2:
                                path = parts[1].strip().strip('"')
                                # $HOME変数を実際のホームディレクトリパスに置換
                                return path.replace("$HOME", str(Path.home()))
            except Exception:
                pass
        # 設定がなければホームディレクトリ直下のDownloadsを返す
        return str(Path.home() / "Downloads")

def get_script_dir():
    """クラスプラットフォームを考慮した、スクリプトファイルあるいは実行ファイルの絶対パスの取得関数"""
    try:
        # PyInstaller, cx_Freeze, Nuitkaによる実行ファイル化後に供えた処理
        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            candidate = os.path.dirname(os.path.abspath(__file__))
            if os.path.isdir(candidate):
                return candidate
            else:
                return os.path.dirname(sys.executable)
        else:
            return os.path.dirname(os.path.abspath(__file__))
    except Exception as ex:
        logger = logging.getLogger()
        logger.error(
            ex,
            exc_info=True
        )

def get_external_path(app_name="YDownloader"):
    """
    OSと実行環境に応じたexternalフォルダーのパスを返します。
    - 開発環境: 実行ファイルと同じディレクトリの下のexternalフォルダー
    - 実行ファイル化後（frozenの場合）：OSごとのユーザーデータディレクトリ内の app_name/external
    - Windows: "C:\\Users\\<ユーザー名>\\AppData\\Local\\YDownloader"
    - macOS: "/Users/<ユーザー名>/Library/Application Support/YDownloader"
    - Linux: "/home/<ユーザー名>/.local/share/YDownloader"
    """
    try:
        logger = logging.getLogger()
    except Exception as ex:
        raise ex
    try:
        # PyInstaller, cx_Freeze, Nuitkaによる実行ファイル化後に供えた処理
        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external")
            if os.path.isdir(candidate): # standaloneモードを考慮
                logger.info(f"standaloneモードで実行されています。external_dir: {candidate}")
                return candidate
            # 実行ファイル化後のユーザー環境
            # OS毎の適切なユーザーディレクトリ
            external_dir = os.path.join(user_data_dir(app_name, roaming=False), "external")
            logger.info(f"実行ファイル化された状態で実行されています。external_dir: {external_dir}")
        else:
            # 開発環境： external フォルダーを使用
            external_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external")
            logger.info(f"開発環境で実行されています。external_dir: {external_dir}")
        return external_dir
    except Exception as ex:
        logger.error(
            ex,
            exc_info=True
        )

def get_configs_path(app_name="YDownloader"):
    """
    OSと実行環境に応じたconfigsフォルダーのパスを返します。
    - 開発環境の場合:
        スクリプトファイルと同じディレクトリ内の "configs" フォルダーを返します。
        例: "C:\\Users\\<ユーザー名>\\Projects\\YDownloader\\configs"
    
    - 実行ファイル化後(frozenの場合)の場合:
        1.  standaloneモードで、実行ファイルと同じディレクトリ内に "configs" フォルダーが存在する場合は、そのパスを返します。
            例: "C:\\Program Files\\YDownloader\\configs"
        2.  standaloneモードでない場合は、OSごとのユーザー設定ディレクトリ内のapp_name/configs を返します。
            例:
                - Windows: "C:\\Users\\<ユーザー名>\\AppData\\Local\\YDownloader\\configs"
                - macOS: "/Users/<ユーザー名>/Library/Application Support/YDownloader/configs"
                - Linux: "/home/<ユーザー名>/.config/YDownloader/configs"
    """
    try:
        logger = logging.getLogger()
    except Exception as ex:
        raise ex
    try:
        # PyInstaller, cx_Freeze, Nuitkaによる実行ファイル化後に供えた処理
        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs")
            if os.path.isdir(candidate): # standaloneモードを考慮
                logger.info(f"standaloneモードで実行されています。configs: {candidate}")
                return candidate
            # 実行ファイル化後のユーザー環境
            # OS毎の適切なユーザーディレクトリ
            configs_dir = os.path.join(user_config_dir(app_name), "configs")
            logger.info(f"実行ファイル化された状態で実行されています。configs: {configs_dir}")
        else:
            # 開発環境：スクリプトディレクトリ直下の external フォルダーを使用
            configs_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "configs")
            logger.info(f"開発環境で実行されています。configs: {configs_dir}")
        return configs_dir
    except Exception as ex:
        logger.error(
            ex,
            exc_info=True
        )

def get_ffmpeg_dir():
    """外部フォルダーとなったffmpegを取得できるようにする"""
    return os.path.join(get_external_path(), "ffmpeg", "bin")

def cleanup_temp_dir(temp_dir):
    """プログラム終了時に一時ディレクトリを削除する関数"""
    logging.info(f"一時ディレクトリを削除中: {temp_dir}")
    shutil.rmtree(temp_dir, ignore_errors=True)

def setup_logging(app_name="YDownloader", loglevel=logging.INFO):
    """ログファイルを使用したログの記録のセットアップ関数(exc_info=Trueで詳細なログを記録)"""
    try:
        global log_file
        # PyInstaller, cx_Freeze, Nuitkaによる実行ファイル化後に供えた処理
        if getattr(sys, "frozen", False) or "__compiled__" in globals():
            candidate = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
            if os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "external")): # standaloneモードを考慮
                log_dir = candidate
            # 実行ファイル化後のユーザー環境
            # OS毎の適切なユーザーディレクトリ
            log_dir = os.path.join(user_data_dir(app_name, roaming=False), "logs")
        else:
            # 開発環境：スクリプトディレクトリ直下の logs フォルダーを使用
            log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")
        logger = logging.getLogger() # globalを使用しなくてもglobal変数が使用される
        logger.setLevel(loglevel)
        # ログファイルにエラー情報や一般的なログを記録する
        # ここでは、平均100バイト/行として、1000行程度で約100KBになるよう設定(調整が必要)
        # 100KBに達すると、バックアップファイルとして一つだけ残され、新しいログファイルが作成される
        rotating_handler = RotatingFileHandler(
            log_file,
            maxBytes=100000, 
            backupCount=1,
            encoding="utf-8"
        )
        # ログのフォーマット設定(時刻、ログレベル、メッセージ)
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        rotating_handler.setFormatter(formatter)
        # loggerにhandlerをセット
        logger.addHandler(rotating_handler)
        logger.info(f"log_dir: {log_dir}")
        # # 開発中(ソースコードのまま)では、コンソールにも出力する
        # console_handler = logging.StreamHandler(sys.stdout)
        # console_handler.setLevel(loglevel) # 必要に応じてレベルをDEBUGにすることでより詳細な情報を得られる
        # console_handler.setFormatter(formatter)
        # logger.addHandler(console_handler)
    except Exception as ex:
        raise ex


def sanitize_filename(filename: str, replacement: str = "_") -> str:
    """
    ファイル名に使用できない文字を削除または置き換える
    Windows, Mac, Linux 全てに対応(ユーザーのOSに合わせて自動調整されるように)
    :param filename:変換したいファイル名
    :param replacement: 置き換え文字(デフォルトは"_")
    :return: 安全なファイル名
    """
    # 禁止文字設定
    if os.name == 'nt': # Windowsの場合
        forbidden_chars = r'[\x00-\x1f\\/*?:"<>|]'
    else: # Linux/macOSの場合
        forbidden_chars = r'[\x00-\x1f/]'  # スラッシュはディレクトリ区切りのため禁止
    # 禁止文字を指定の文字(デフォルト"_")に置換
    filename = re.sub(forbidden_chars, replacement, filename)
    # Windowsでは先頭・末尾の空白やピリオドを削除
    if os.name == 'nt':
        filename = filename.strip(" .")
        # Windowsの予約デバイス名を回避
        reserved_names = {
            "CON", "PRN", "AUX", "NUL",
            *(f"COM{i}" for i in range(1, 10)),
            *(f"LPT{i}" for i in range(1, 10)),
        }
        if filename.upper() in reserved_names:
            filename += "_safe"
    # 空のファイル名を回避
    return filename if filename else "default_filename"

# エラーダイアログ用　エラーダイアログは最初にページに対して追加する事
def close_dlg(e, err_dlg, page):
    page.close(err_dlg)
    page.update()

def open_dlg(err_dlg, page):
    page.open(err_dlg)
    page.update()

class DefaultSettingsLoader:
    """
    設定ローダー
    
    設定項目:
    -retry_chance: リトライ回数(整数)
    -show_progress: プログレス表示の有無(True/False)
    -content_type: "movie"または"music"
    -movie_quality: 動画ダウンロード時のformat文字列
    -movie_format: 動画ダウンロード時のファイル形式
    -music_quality: 音楽ダウンロード時のformat文字列
    -music_format: 音楽ダウンロード時のファイル形式
    -download_dir: 保存先ディレクトリ(指定があれば、それに従うが、指定がない場合、各OSのダウンロードフォルダーになる)
    -temp_dir: 一時ファイル保存場所(ユーザー操作なしを想定)。基本的には、スクリプトファイルがあるディレクトリの下
    -page_theme: アプリ全体のテーマ("LIGHT"または"DARK")
    """
    
    def __init__(self):
        self.logger = logging.getLogger()
        self.logger.debug("DefaultSettingsLoaderの__init__開始")
        
        # このスクリプトが存在するディレクトリの絶対パスを取得
        self.SCRIPT_DIR = get_script_dir()
        # config.jsonへのパスを作成
        self.CONFIG_PATH = os.path.join(get_configs_path(), "config.json")
        self.logger.info(f"config.json: {self.CONFIG_PATH}")
        # 一時ディレクトリを作成
        # atexitを使用してプログラム終了時に削除されるようにする
        self.TEMP_DIR = tempfile.mkdtemp()
        self.logger.info(f"一時ディレクトリが作成されました: {self.TEMP_DIR}")
        # プログラム終了時にcleanup_temp_dir()を実行するよう登録
        atexit.register(lambda: cleanup_temp_dir(self.TEMP_DIR))
        self.logger.info("atexitを使用して一時ディレクトリ削除をプログラム終了時にreigisterしました")
        
        self.download_folder = get_download_folder()
        # 許可される設定キー定義(コード編集なしでの変更禁止)
        self.ALLOWED_KEYS = frozenset({
            "retry_chance", 
            "show_progress",
            "content_type",
            "movie_quality",
            "movie_format",
            "music_quality",
            "music_format",
            "download_dir",
            "temp_dir",
            "page_theme"
        })
        
        self.logger.debug("ALLOWED_KEYS読み込み完了")
        # logger.error("エラー発生", exc_info=True)  # ← `exc_info=True` で詳細なログを記録
        # ファイルが存在しない時はエラー
        # 致命的なエラーのため、アプリ実行自体を中止
        if not os.path.exists(self.CONFIG_PATH):
            self.logger.error(
                f"設定ファイル{self.CONFIG_PATH}が見つかりません。致命的なエラーのため、実行を中止します。", 
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise FileNotFoundError(f"{self.CONFIG_PATH}が見つかりません。")
        # JSONファイルを読み込み
        with open(self.CONFIG_PATH, "r", encoding="utf-8") as f:
            self._config_data = json.load(f)
        # JSON内のキーが許可されるキーと完全一致しているかチェック
        if set(self._config_data.keys()) != self.ALLOWED_KEYS:
            self.logger.error(
                f"設定ファイル内のキーが正しくありません。許可されるキー: {self.ALLOWED_KEYS}, 現在のキー: {set(self._config_data.keys())}",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise KeyError("config.jsonのキーが正しくありません。")
        # ALLOWED_KEYSの各キーに対して非公開インスタンス変数を自動生成
        for key in self.ALLOWED_KEYS:
            if key == "download_dir" and not self._config_data[key]:
                setattr(self, f"_{key}", self.download_folder)
            elif key == "temp_dir" and not self._config_data[key]:
                setattr(self, f"_{key}", self.TEMP_DIR)
            else:
                setattr(self, f"_{key}", self._config_data[key])
        self.logger.debug(self._config_data)
    
    def update_setting(self, key, value):
        """
        設定値を変更するメソッド(クラス内からのみ使用)
        変更後は、config.jsonファイルも更新する。
        """
        if key not in self.ALLOWED_KEYS:
            self.logger.error(
                f"設定 '{key}' は存在しません。",
                exc_info=True
            )
            # sys.exit(1)
            raise KeyError("config.jsonに正しいkeyでアクセスしてください。")
        
        try:
            # メモリ上の値を更新
            setattr(self, f"_{key}", value)
            self._config_data[key] = value
            
            # config.jsonファイルを更新
            with open(self.CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config_data, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            # 更新に失敗した場合は元の値に戻す
            if hasattr(self, f"_{key}"):
                original_value = getattr(self, f"_{key}")
                setattr(self, f"_{key}", original_value)
                self._config_data[key] = original_value
            self.logger.error(
                f"設定の更新に失敗しました。key: {key}, Exception: {ex}",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ex
    
    def __getattr__(self, key):
        """外部からのアクセス用(_を付けた非公開変数を参照)"""
        if key in self.ALLOWED_KEYS:
            return getattr(self, f"_{key}")
        self.logger.error(
            f"'{type(self).__name__}' オブジェクトに属性 '{key}' は存在しません。",
            exc_info=True
        )
        # sys.exit(1) # プログラムの終了
        raise KeyError("正しいkeyでアクセスしてください。")
    
    def __setattr__(self, key, value):
        """外部からの直接変更を禁止"""
        # ここでgetattrを使用すると再帰エラーが発生する
        if "_config_data" in self.__dict__ and key in self.ALLOWED_KEYS:
            self.logger.error(
                f"'{key}' は直接変更できません。'update_setting()'を使用してください。",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ValueError("update_setting()を使用してください。")
        super().__setattr__(key, value) # 通常の動作

class Download:
    def __init__(self, settings):
        self.settings = settings
        self.logger = logging.getLogger()
        self.logger.debug("Downloadの__init__開始")
        self.ffmpeg_dir = get_ffmpeg_dir()
        self.logger.debug(f"{self.ffmpeg_dir}がffmpeg_dirです。")
        self.save_dir = os.path.join(settings.download_dir, "YDownloader")
        os.makedirs(self.save_dir, exist_ok=True)
        self.retries = settings.retry_chance
        self.show_progress = settings.show_progress
        self.content_type = settings.content_type
        os.makedirs(self.save_dir, exist_ok=True)
        self.temp_dir = settings.temp_dir
        self.cards = {}
    
    def _check_network(self, host="8.8.8.8", port=53, timeout=3):
        """
        指定したホストとポートへの接続が可能かどうかチェックして、端末のネットワーク接続が正常かどうか検査する
        デフォルトでは、GoogleのDNSサーバー(8.8.8.8)の53番ポートを使用。
        """
        try:
            socket.setdefaulttimeout(timeout)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect((host, port))
            return True
        except socket.error:
            return False
    
    def _check_content_type(self, key=None, page=None):
        """
        ダウンロードしたいコンテンツタイプに応じて、ダウンロード関数を適宜実施する関数
        
        :param key: Card要素検索のためのkey
        :param page: Fletのpage
        """
        if not key or not page:
            self.logger.error(
                "keyまたはpageの値が不正です。",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ValueError("keyまたはpageの値が不正です。")
        info_path = os.path.join(self.temp_dir, f"{key}.json")
        with open(info_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        url = data.get("url", None)
        if not url:
            self.logger.error(
                "JSONファイルにおけるurlの値が不正です。",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ValueError("JSONファイルにおけるurlの値が不正です。")
        title = data.get("title", "Unknown Title")
        # uploader = data.get("uploader", "Unknown") # 後で作曲者とかの部分に使用したい
        content_type = data.get("content_type", None)
        is_entries = data.get("is_entries", False)
        if not is_entries:
            if content_type == "movie":
                abema_url = "https://abema.tv"
                if url.startswith(abema_url):
                    self.logger.info("yt-dlpコマンドを実行します。")
                    command = [
                        "yt-dlp",
                        "--output", os.path.join(self.save_dir, "%(title)s.%(ext)s"),
                        "--ffmpeg-location", self.ffmpeg_dir,
                        url
                    ]
                    process = subprocess.Popen(
                        command,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,
                        encoding="utf-8"
                    )
                    for line in process.stdout:
                        self.logger.info(line.strip()) # ログに出力
                    stderr_output, _ = process.communicate()
                    if stderr_output:
                        self.logger.error(stderr_output.strip())
                else:
                    self.logger.info(f"self.download_movieを{url},{title}に対して実行します")
                    self.download_movie(url=url, filename=title, key=key, page=page)
            elif content_type == "music":
                self.logger.info(f"self.download_musicを{url},{title}に対して実行します")
                self.download_music(url=url, filename=title, key=key, page=page)
            else:
                self.logger.error(
                    "content_typeの値が不正です。",
                    exc_info=True
                )
                open_dlg(content_type_err_dlg, page)
        else:
            # print("これは正常にメタデータが記録されたプレイリスト") # デバッグ用
            try:
                entries = data.get("entries", None)
                save_dir = os.path.join(self.save_dir, title)
                os.makedirs(save_dir, exist_ok=True)
                if not entries:
                    self.logger.error(
                        f"entriesの値が不正です: {entries}",
                        exc_info=True
                    )
                    # sys.exit(1) # プログラムの終了
                    raise ValueError("entriesの値が不正です。")
                if content_type == "movie":
                    abema_url = "https://abema.tv"
                    if url.startswith(abema_url):
                        self.logger.info("yt-dlpコマンドを実行します。")
                        command = [
                            "yt-dlp",
                            "--output", os.path.join(save_dir, "%(title)s.%(ext)s"),
                            "--ffmpeg-location", self.ffmpeg_dir,
                            url
                        ]
                        process = subprocess.Popen(
                            command,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE,
                            text=True,
                            encoding="utf-8"
                        )
                        for line in process.stdout:
                            self.logger.info(line.strip()) # ログに出力
                        stderr_output, _ = process.communicate()
                        if stderr_output:
                            self.logger.error(stderr_output.strip())
                    else:
                        for index, entry in enumerate(entries):
                            self.logger.info(f"{index + 1}番目のコンテンツをダウンロードします")
                            entry_title = entry.get("title", None)
                            entry_url = entry.get("url", None)
                            if not entry_title or not entry_url:
                                self.logger.warning(
                                    f"{index + 1}番目のentryのtitleまたはurlの値が不正です。",
                                    exc_info=True
                                )
                                continue # スキップ
                            result = self.download_movie(
                                url=entry_url,
                                filename=entry_title,
                                content_save_dir=save_dir, 
                                page=page,
                                is_entries=True
                            )
                            if result == "NetWorkError":
                                self.logger.error(
                                    "Movie download failed for NetWork Error",
                                    exc_info=True
                                )
                                open_dlg(network_err_dlg, page)
                                break # ループを中断
                            elif not result:
                                self.logger.error(
                                    "Movie download failed. Stopping the process.",
                                    exc_info=True
                                )
                                open_dlg(playlist_error_dlg, page)
                                break # ループを中断
                    self.logger.info(f"Download process complete. Executing post-download code. url: {url}")
                    self._fire_after_download(key=key, page=page)
                    self.logger.info(f"Movie download completed in format: {settings.movie_format}")
                elif content_type == "music":
                    for index, entry in enumerate(entries):
                        self.logger.info(f"{index + 1}番目のコンテンツをダウンロードします")
                        entry_title = entry.get("title", None)
                        entry_url = entry.get("url", None)
                        if not entry_title or not entry_url:
                            self.logger.warning(
                                f"{index + 1}番目のentryのtitleの値が不正です。",
                                exc_info=True
                            )
                            continue # スキップ
                        result = self.download_music(
                            url=entry_url,
                            filename=entry_title, 
                            content_save_dir=save_dir, 
                            page=page,
                            is_entries=True
                        )
                        if result == "NetWorkError":
                            self.logger.error(
                                "Music download failed for NetWork Error",
                                exc_info=True
                            )
                            open_dlg(network_err_dlg, page)
                            break # ループを中断
                        elif not result:
                            self.logger.error(
                                "Music download failed. Stopping the process.",
                                exc_info=True
                            )
                            open_dlg(playlist_error_dlg, page)
                            break # ループを中断
                    self.logger.info(f"Download process complete. Executing post-download code. url: {url}")
                    self._fire_after_download(key=key, page=page)
                    self.logger.info(f"Music download completed in format: {settings.music_format}")
                else:
                    self.logger.error(
                        "content_typeの値が不正です。",
                        exc_info=True
                    )
                    open_dlg(content_type_err_dlg, page)
            except Exception as ex:
                self.logger.error(
                    ex,
                    exc_info=True
                )
                # sys.exit(1) # プログラムの終了
                raise ex
    
    def _fire_after_download(self, key=None, page=None):
        """
        ダウンロード完了後の処理
        完了したkeyのCardのdisabledにしたボタンやテキストフィールドのdisabledを解除する
        """
        print("Post-download processing is now executed.")
        try:
            if not key or not page:
                self.logger.error(
                    "keyまたはpageの値が不正です。",
                    exc_info=True
                )
                # sys.exit(1) # プログラムの終了
                raise ValueError("keyまたはpageの値が不正です。")
            target_card = self.cards[key]
            target_column = target_card.content.content
            target_info = target_column.controls[0]
            target_progress_bar = target_column.controls[1].content
            target_about_info = target_info.controls[1]
            target_title = target_about_info.controls[0]
            target_uploader = target_about_info.controls[1].controls[0]
            target_content_type = target_about_info.controls[1].controls[1].controls[0]
            download_button = target_info.controls[2].controls[0]
            delete_button = target_info.controls[2].controls[1]
            download_button.disabled = False  # ダウンロードボタンを有効化
            delete_button.disabled = False # デリートボタンを有効化
            target_title.disabled = False # タイトル入力欄を有効化
            target_content_type.disabled = False # ダウンロードタイプ選択有効化
            target_uploader.disabled = False # 投稿者テキストフィールド有効化
            target_progress_bar.visible = False # プログレスバーが見えなくする
            page.update()
        except Exception as ex:
            self.logger.error(
                ex,
                exc_info=True
            )
            # sys.exit(1)
            raise ex
    
    # コメント取得用関数を考えておく
    
    def download_movie_for_abema(self, urls=False, outtmpl=None, content_save_dir=False, ffmpeg_location=None):
        """
        Abemaでの動画ダウンロードにチャレンジする用の関数
        
        :param urls: ダウンロード対象のコンテンツURL(Falseの場合はエラー)(リストで渡されるから避けてsubprocessに渡す)
        :param outtmpl: 保存する際のファイル名(拡張子は自動付与)
        :param content_save_dir: 保存する際のディレクトリ(プレイリストだとプレイリスト名のフォルダーを作ってその中に保存する)(デフォルトはself.save_dir)
        """
        if not urls or not ffmpeg_location:
            self.logger.error(
                "Error: url or ffmpeg_location is not defined",
                exc_info=True
            )
            # sys.exit(1)
            raise FileNotFoundError("ffmpeg_locationが定義されていません。")
        if not content_save_dir:
            content_save_dir = self.save_dir
        
        ydl_opts = {
            "format": "best",
            "outtmpl": outtmpl,
            "ffmpeg_location": self.ffmpeg_dir,
        }
        try:
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download(urls)
            self.logger.info("Success for downloading for abema")
            return True
        except Exception as ex:
            self.logger.error(
                "Error: in download_movie_for_abema",
                exc_info=True
            )
            return False
    
    def download_movie(self, url=False, filename=None, content_save_dir=False, key=None, page=None, is_entries=False):
        """
        指定されたURLの動画をダウンロードする。
        settings.content_typeが "movie" の場合、実行される。
        動画品質は、settings.movie_qualityをもとに選択される。
        ファイル形式は、settings.movie_formatをもとに選択される。
        
        :param url: ダウンロード対象のコンテンツURL(Falseの場合はエラー)
        :param filename: 保存する際のファイル名(拡張子は自動付与)
        :param content_save_dir: 保存する際のディレクトリ(プレイリストだとプレイリスト名のフォルダーを作ってその中に保存する)(デフォルトはself.save_dir)
        :param key: Card要素検索のためのkey
        :param page: Fletのpage
        :param is_entries: プレイリスト向け処理用のオプション(デフォルトはFalse)
        """
        if not url or not page:
            self.logger.error(
                "Error: url or page is not defined",
                exc_info=True
            )
            # sys.exit(1)
            raise ValueError("urlまたはpageが定義されていません。")
        if not key and not is_entries:
            self.logger.error(
                "Error: key is not defined for not entries case",
                exc_info=True
            )
            # sys.exit(1)
            raise ValueError("プレイリスト向けのkeyが定義されていません。")
        if not content_save_dir:
            content_save_dir = self.save_dir
        
        # URLをリストに変換(既にリストの場合はそのまま)
        # こうすることで、インスタンス作成数を減らせるし、将来的なバージョンアップにも対応しやすい
        urls = [url] if isinstance(url, str) else url
        
        quality_format = settings.movie_quality
        movie_format = settings.movie_format
        self.logger.debug(quality_format, movie_format)
        
        # filenameが指定されていれば、その名前に拡張子を付与して保存する
        if filename:
            outtmpl = os.path.join(content_save_dir, f"{filename}.%(ext)s")
        else:
            outtmpl = os.path.join(content_save_dir, "%(title)s.%(ext)s")
        self.logger.debug(outtmpl)
        
        ydl_opts = {
            "format": quality_format,
            "outtmpl": outtmpl,
            "merge_output_format": movie_format,
            "ffmpeg_location": self.ffmpeg_dir,
            "postprocessors": [
                {
                    "key": "FFmpegVideoRemuxer",
                    "preferedformat": movie_format,
                }
            ],
            "postprocessor_args": ["-c:a", "aac"],  # FFmpeg に音声を AAC に変換させる
            "updatetime": False,  # これを追加
            "verbose": True,
        }
        
        attempt = 0
        while attempt < self.retries:
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(urls) # リストとして渡す
                # ここで、全てのダウンロード処理(およびマージ)が完了しているので、終了処理を一度だけ呼ぶ
                # プレイリストでない時は別の個所で終了処理を行う(ダウンロード関数は繰り返されるため)
                if not is_entries:
                    self.logger.info("Download process complete. Executing post-download code.")
                    self._fire_after_download(key=key, page=page)
                    self.logger.info(f"Movie download completed in format: {movie_format}")
                return True
            except Exception as ex:
                if not self._check_network():
                    if not is_entries:
                        self.logger.error(
                            "A network error occurred. Please check your connection and try again.",
                            exc_info=True
                        )
                        open_dlg(network_err_dlg, page)
                        self._fire_after_download(key=key, page=page)
                    return "NetWorkError"
                attempt += 1
                self.logger.info(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    if not is_entries:
                        self.logger.error(
                            "Max retry limit reached. Aborting movie download. Try download_movie_for_abema.",
                            exc_info=True
                        )
                        result = self.download_movie_for_abema(urls=urls, outtmpl=outtmpl, content_save_dir=content_save_dir, ffmpeg_location=self.ffmpeg_dir)
                        if not result:
                            open_dlg(retry_error_dlg, page)
                        self._fire_after_download(key=key, page=page)
                        return False
                    else:
                        self.logger.info("Try download_movie_for_abema")
                        result = self.download_movie_for_abema(urls=urls, outtmpl=outtmpl, content_save_dir=content_save_dir, ffmpeg_location=self.ffmpeg_dir)
                        if not result:
                            return False
                        else:
                            return True
    
    def download_music(self, url=False, filename=None, content_save_dir=False, key=None, page=None, is_entries=False):
        """
        指定されたURLの音楽をダウンロードする。
        settings.content_typeが "music" の場合、実行される。
        音楽品質は、settings.music_qualityをもとに選択される。
        ファイル形式は、settings.music_formatをもとに選択される。
        
        :param url: ダウンロード対象のコンテンツURL(Falseの場合はエラー)
        :param filename: 保存する際のファイル名(拡張子は自動付与)
        :param content_save_dir: 保存する際のディレクトリ(プレイリストだとプレイリスト名のフォルダーを作ってその中に保存する)(デフォルトはself.save_dir)
        :param key: Card要素検索のためのkey
        :param page: Fletのpage
        :param is_entries: プレイリスト向け処理用のオプション(デフォルトはFalse)
        """
        if not url or not page:
            self.logger.error(
                "Error: url or page is not defined",
                exc_info=True
            )
            # sys.exit(1)
            raise ValueError("urlまたはpageが定義されていません。")
        if not key and not is_entries:
            self.logger.error(
                "Error: key is not defined for not entries case",
                exc_info=True
            )
            # sys.exit(1)
            raise ValueError("プレイリスト向けのkeyが適切に定義されていません。")
        if not content_save_dir:
            content_save_dir = self.save_dir
        
        # URLをリストに変換(既にリストの場合はそのまま)
        # こうすることで、インスタンス作成数を減らせるし、将来的なバージョンアップにも対応しやすい
        urls = [url] if isinstance(url, str) else url
        
        quality_format = settings.music_quality
        music_format = settings.music_format
        self.logger.debug(quality_format, music_format)
        
        # filenameが指定されていれば、その名前に拡張子を付与して保存する
        if filename:
            outtmpl = os.path.join(content_save_dir, f"{filename}.%(ext)s")
        else:
            outtmpl = os.path.join(content_save_dir, "%(title)s.%(ext)s")
        self.logger.debug(outtmpl)
        
        ydl_opts = {
            "format": quality_format,
            "outtmpl": outtmpl,
            "ffmpeg_location": self.ffmpeg_dir,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": music_format,
                "preferredquality": "192", # ビットレート(今後設定ファイルから制御可能にする)
            }],
            "updatetime": False,  # これを追加
            "verbose": True,
        }
        
        attempt = 0
        while attempt < self.retries:
            try:
                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download(urls)
                # ここで、全てのダウンロード処理(およびマージ)が完了しているので、終了処理を一度だけ呼ぶ
                # プレイリストでない時は別の個所で終了処理を行う(ダウンロード関数は繰り返されるため)
                if not is_entries:
                    self.logger.info("Download process complete. Executing post-download code.")
                    self._fire_after_download(key=key, page=page)
                    self.logger.info(f"Music download completed in format: {music_format}")
                return True
            except Exception as ex:
                if not self._check_network():
                    if not is_entries:
                        self.logger.error(
                            "A network error occurred. Please check your connection and try again.",
                            exc_info=True
                        )
                        open_dlg(network_err_dlg, page)
                        self._fire_after_download(key=key, page=page)
                    return "NetWorkError"
                attempt += 1
                self.logger.info(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    if not is_entries:
                        self.logger.error(
                            "Max retry limit reached. Aborting music download. Try yt-dlp command.",
                            exc_info=True
                        )
                        open_dlg(retry_error_dlg, page)
                        self._fire_after_download(key=key, page=page)
                    return False

class YDownloader:
    def __init__(self, settings, downloader):
        # 設定やグローバル変数相当の初期化
        self.logger = logging.getLogger()
        self.logger.debug("YDownloaderの__init__開始")
        self.ffmpeg_dir = get_ffmpeg_dir()
        self.logger.debug(f"{self.ffmpeg_dir}がffmpeg_dirです。")
        self.retries = settings.retry_chance
        self.temp_dir = settings.temp_dir
        self.pre_url_list = []
        self.pre_total_urls = 0
        self.pre_current_urls = 0
        self.cards = {}
        self.added_urls = []
        self.condition_pre = threading.Condition()
        self.downloader = downloader
    
    def preview_video_info(self, url, page):
        """
        指定URLの動画情報を取得し、一時ディレクトリにJSONとして保存する。
        GUIでの表示用に動画のサムネイル画像、タイトル、投稿日時を取得して、一時ファイルとして保存する。
        アプリが正常終了する時に、一時ファイルはそのフォルダーごと削除する。
        アプリが異常終了したときは、すぐに復帰できるように、一時ファイルは削除しない。
        
        :param url: 動画のURL
        :param page: Fletのpage
        """
        if not url:
            self.logger.error(
                "Error: url is not defined",
                exc_info=True
            )
            # sys.exit(1)
            raise ValueError("urlの値が定義されていません。")
        
        ydl_opts = {
            "skip_download": True, # 動画本体はダウンロードしない
            "quiet": True, # 進捗状況を表示しない
            "ffmpeg_location": self.ffmpeg_dir,
            # "verbose": True,  # 詳細なデバッグ情報を表示
            "verbose": True,
        }
        attempt = 0
        while attempt < self.retries:
            try:
                self.logger.debug(f"{url}に対してpreview_video_infoを実行します。")
                with YoutubeDL(ydl_opts) as ydl:
                    # 動画情報を取得
                    info = ydl.extract_info(url, download=False)
                # このままだとプレイリストがまとまる
                # そして、それをダウンロードしようとすると中身をすべてプレイリストの名前で保存しようとするため、上書き保存されてしまう
                # プレイリストならばプレイリスト名でフォルダーを作成して、そのなかにプレイリストの中身の動画を底にダウンロードするように変更する
                # print(json.dump(info, indent=2, ensure_ascii=False)) # デバッグ用
                if not info:
                    self.logger.error(
                        f"Error: Could not retrieve information for {url}",
                        exc_info=True
                    )
                    # ここで終了しないと後続処理がエラーになる
                    # sys.exit(1)
                    raise ValueError("適切な動画情報が取得できませんでした。")
                # ユニークなIDを生成
                unique_id = str(uuid.uuid4().hex)
                # タイトルを取得して安全なファイル名に変換
                title = info.get("title", "Unknown Title")
                safe_title = sanitize_filename(title)
                # 動画の投稿者名を取得
                uploader = info.get("uploader", "Unknown Uploader")
                # 動画の概要欄情報の取得
                overview = info.get("description", None)
                # サムネイル画像の保存
                thumbnail_path = None
                try:
                    thumbnail_url = info.get("thumbnail", None)
                    if thumbnail_url:
                        thumb_filename = f"{unique_id}_thumb.jpg"
                        thumbnail_path = os.path.join(self.temp_dir, thumb_filename)
                        response = requests.get(thumbnail_url)
                        with open(thumbnail_path, "wb") as f:
                            f.write(response.content)
                except Exception as ex:
                    self.logger.error(
                        f"Error: {ex}",
                        exc_info=True
                    )
                    # sys.exit(1) # プログラムの終了
                    raise ex
                # 投稿日時のフォーマット
                upload_date = info.get("upload_date", "Unknown Date")
                if upload_date and upload_date != "Unknown Date":
                    upload_date = datetime.strptime(upload_date, "%Y%m%d").strftime("%Y年%m月%d日")
                # entriesがあればプレイリストと判定できる
                entries = info.get("entries", None)
                if entries:
                    self.logger.debug("これはプレイリストです")
                    entries_numbers = len(entries)
                    extracted_entries = []
                    for index, entry in enumerate(entries):
                        entry_safe_title = sanitize_filename(entry.get("title", None))
                        entry_url = entry.get("webpage_url", None)
                        entry_uploader = entry.get("uploader", "Unknown Uploader")
                        entry_upload_date = entry.get("uploader", "Unknown Uploader")
                        entry_overview = entry.get("description", None)
                        if not entry_safe_title or not entry_url:
                            self.logger.info(f"entry {index} は無効なデータの為、スキップされました")
                            continue # スキップ
                        extracted_entries.append(
                            {
                                # idはいらない
                                "index": index,
                                "title": entry_safe_title,
                                "url": entry_url,
                                "uploader": entry_uploader,
                                "upload_date": entry_upload_date,
                                "overview": entry_overview
                            }
                        )
                    preview_info = {
                        "id": unique_id,
                        "title": safe_title,
                        "upload_date": upload_date,
                        "uploader": uploader,
                        "overview": overview,
                        "thumbnail_path": thumbnail_path,
                        "url": url,
                        "is_playlist": False,
                        "content_type": settings.content_type,
                        "is_entries": True,
                        "numbers": entries_numbers,
                        "entries": extracted_entries,
                    }
                else:
                    # 保存する情報を整理
                    preview_info = {
                        "id": unique_id,
                        "title": safe_title,
                        "upload_date": upload_date,
                        "uploader": uploader,
                        "overview": overview,
                        "thumbnail_path": thumbnail_path,
                        "url": url,
                        "is_playlist": False,
                        "content_type": settings.content_type,
                    }
                # JSON形式で保存
                info_filename = f"{unique_id}.json"
                info_path = os.path.join(self.temp_dir, info_filename)
                with open(info_path, "w", encoding="utf-8") as f:
                    json.dump(preview_info, f, ensure_ascii=False, indent=2)
                return info_path
            except Exception as ex:
                if not self.downloader._check_network():
                    self.logger.error(
                        "A network error occurred. Please check your connection and try again.",
                        exc_info=True
                    )
                    return "NetWorkError"
                # エラーメッセージにプレイリスト特有の警告が含まれている場合は、プレイリストとして最低限の情報を記録する
                if "Incomplete data received" in str(ex) or "youtube:tab" in str(ex):
                    self.logger.info(
                        "プレイリストとみなせるエラーが発生したため、最低限のプレイリスト情報を記録します。",
                        exc_info=True
                    )
                    unique_id = str(uuid.uuid4().hex)
                    playlist_info = {
                        "id": unique_id,
                        "url": url,
                        "is_playlist": True,
                        "content_type": settings.content_type,
                    }
                    info_filename = f"{unique_id}.json"
                    info_path = os.path.join(self.temp_dir, info_filename)
                    with open(info_path, "w", encoding="utf-8") as f:
                        json.dump(playlist_info, f, ensure_ascii=False, indent=2)
                    return info_path
                attempt += 1
                self.logger.info(f"Attempt {attempt} failed: {ex}")
                if attempt >= self.retries:
                    self.logger.error(
                        f"動画情報の取得に失敗しました: {ex}",
                        exc_info=True
                    )
                    return None
    
    def compute_perfect_size(self, page: ft.Page, thumb_width, thumb_height, key):
        """
        ページのウィンドウサイズから16:9枠内に収まるフレームサイズを計算し、
        サムネイル画像サイズ(又は、画像がない場合はプレースホルダー(灰色画像を生成して保存))を返す。
        """
        if not key:
            self.logger.error(
                "keyの値が不明です。",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise KeyError("keyの値が不明です。")
        frame_width = int(page.window.width / 4)
        frame_height = int(frame_width * 9 / 16)
        if thumb_width == 0 or thumb_height == 0:
            # サムネイル画像がない場合は、プレースホルダー画像を生成する
            img = Image.new("RGB", (1280, 720), (128, 128, 128))
            thumbnail_path = os.path.join(self.temp_dir, f"{key}_thumb.jpg")
            img.save(thumbnail_path, format="JPEG", quality=95) # JPG形式で保存
            return {
                "src": thumbnail_path, 
                "width": frame_width,
                "height": frame_height
            }
        else:
            if int(thumb_height) > int(thumb_width * 9 / 16):
                background_width = int(thumb_height * 16 / 9)
                background_height = int(thumb_height)
            else:
                background_width = int(thumb_width)
                background_height = int(thumb_width * 9 / 16)
            offset_x = int((background_width - thumb_width) / 2)
            offset_y = int((background_height - thumb_height) / 2)
            return {
                "width": background_width,
                "height": background_height,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "frame_width": frame_width,
                "frame_height": frame_height
            }
    
    # 動画読み込み後のカード追加用関数
    def add_video_card(self, page: ft.Page):
        """
        URLリストからURLを取り出し、動画情報を取得してカードを生成し、ページに追加する。
        ※無限ループ内でスレッドとして実行する
        """
        while True:
            with self.condition_pre:
                while not self.pre_url_list:
                    self.pre_total_urls = 0
                    self.pre_current_urls = 0
                    self.progress.visible = False # 進捗バー見えないように
                    self.progress.controls[1].value = 0 # progress_textのvalue
                    self.progress.controls[0].content.value = 0 # progress_barのvalue
                    page.update()
                    self.condition_pre.wait()
                print(self.pre_url_list) # デバッグ用
                url = self.pre_url_list.pop(0) # pop(0)で先頭のURLを取得してリストから削除
                self.progress.visible = True # 取り込み開始なので表示
                self.progress.controls[1].value = f"{self.pre_current_urls + 1}/{self.pre_total_urls}" # progress_textのvalue
                self.progress.controls[0].content.value = (self.pre_current_urls / self.pre_total_urls) if self.pre_total_urls > 0 else 0 # progress_barのvalue
                page.update()
            try:
                self.pre_current_urls += 1
                json_path = self.preview_video_info(url, page)
                self.logger.debug(json_path)
                if json_path == "NetWorkError":
                    open_dlg(network_err_dlg, page)
                elif not json_path:
                    open_dlg(link_err_dlg, page)
                else:
                    self.logger.debug(f"Generated JSON path: {json_path}")
                    with open(json_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.logger.debug(f"data: {data}")
                    is_playlist = data.get("is_playlist", "ERROR")
                    if is_playlist == "ERROR":
                        self.logger.error(
                            "is_playlistの値が不正です。",
                            exc_info=True
                        )
                        # sys.exit(1) # プログラムの終了
                        raise ValueError("is_playlistの値が不正です。")
                    # 各Cardに追加されるkey
                    key = data.get("id", "Unknown ID")
                    if key == "Unknown ID":
                        self.logger.error(
                            "IDが不明です。",
                            exc_info=True
                        )
                        # sys.exit(1) # プログラムの終了
                        raise ValueError("IDが不明です。")
                    is_entries = data.get("is_entries", False)
                    if is_entries:
                        print("これは正常にメタデータを入手できたプレイリスト") # デバッグ用
                        entry_video_title = ft.TextField(
                            label="タイトル",
                            value=data.get("title", "Unknown Title"),
                            adaptive=True,
                        )
                        entry_video_date = ft.Text(
                            value=data.get("upload_date", "Unknown"),
                        )
                        entry_video_uploader = ft.TextField(
                            label="投稿者",
                            value=data.get("uploader", "Unknown"),
                            adaptive=True,
                        )
                        entry_thumbnail_img_src = data.get("thumbnail_path", None)
                        if not entry_thumbnail_img_src:
                            # サムネイルがない場合は、compute_perfect_sizeでプレースホルダー画像を生成
                            entry_placeholder = self.compute_perfect_size(page, 0, 0, key)
                            entry_video_thumbnail_img = ft.Image(
                                src=entry_placeholder["src"],
                                width=entry_placeholder["width"],
                                height=entry_placeholder["height"],
                                fit=ft.ImageFit.CONTAIN,
                                border_radius=ft.border_radius.all(10),
                            )
                        else:
                            # 画像を読み込み、16:9の枠内に収まるように中央配置した背景画像を作成
                            with Image.open(entry_thumbnail_img_src) as img:
                                entry_img_width, entry_img_height = img.size
                                entry_perfect_img_size = self.compute_perfect_size(page, entry_img_width, entry_img_height, key)
                                # 灰色の背景画像作成
                                # リサイズはなし
                                entry_background = Image.new("RGB", (entry_perfect_img_size["width"], entry_perfect_img_size["height"]), (128, 128, 128))
                                entry_background.paste(img, (entry_perfect_img_size["offset_x"], entry_perfect_img_size["offset_y"]))
                                # サムネイル画像配置枠
                                entry_frame_width = entry_perfect_img_size["frame_width"]
                                entry_frame_height = entry_perfect_img_size["frame_height"]
                                # .temp内の一時ファイルに保存
                                with tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir, suffix=".jpg") as entry_temp_file:
                                    entry_temp_path = entry_temp_file.name
                                    entry_background.save(entry_temp_path, format="JPEG", quality=95) # JPG形式で保存
                            # 元のファイルをバックアップ
                            entry_backup_path = entry_thumbnail_img_src + ".bak"
                            os.rename(entry_thumbnail_img_src, entry_backup_path)
                            # 一時ファイルを元のファイルに置き換え
                            os.rename(entry_temp_path, entry_thumbnail_img_src)
                            # バックアップ削除(上書きが成功した場合)
                            os.remove(entry_backup_path)
                            entry_video_thumbnail_img = ft.Image(
                                src=entry_thumbnail_img_src,
                                width=entry_frame_width,
                                height=entry_frame_height,
                                fit=ft.ImageFit.CONTAIN,
                                border_radius=ft.border_radius.all(10),
                            )
                        # RadioGroupを作成
                        # 保存形式を個々に選択できるようにする(MovieとMusic)
                        entry_rg = ft.RadioGroup(
                            value=settings.content_type,
                            content=ft.Row([
                                ft.Radio(value="movie", label="Movie"),
                                ft.Radio(value="music", label="Music"),
                            ]),
                        )
                        # lambda式の「遅延束縛」を回避するためにデフォルト引数としてkeyをバインドする
                        entry_delete_icon = ft.IconButton(
                            icon=ft.Icons.DELETE_FOREVER_ROUNDED,
                            on_click=lambda e, key=key : self.remove_card(e, key, page, url),
                            tooltip="削除",
                        )
                        entry_download_icon = ft.IconButton(
                            icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                            on_click=lambda e, key=key: self.download_video_by_key(e, key, page),
                            tooltip="ダウンロード",
                        )
                        entry_progress = ft.ProgressBar(
                            visible=False,
                            value=None,
                        )
                        entry_progress_container = ft.Container(
                            content=entry_progress,
                            expand=True, # 親であるCardの幅いっぱいに広がるように
                            clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                            border_radius=ft.border_radius.all(8),
                        )
                        entry_about_info = ft.Column(
                            controls=[
                                entry_video_title,
                                ft.Row(
                                    controls=[
                                        entry_video_uploader,
                                        ft.Row(
                                            controls=[
                                                entry_rg,
                                                ft.Column(
                                                    controls=[
                                                        entry_video_date,
                                                        ft.Text(
                                                            value=f"{data.get('numbers', 'Unknown')}個"
                                                        ),
                                                    ],
                                                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                                                ),
                                            ],
                                            alignment=ft.MainAxisAlignment.END,
                                        ),
                                    ],
                                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                ),
                            ],
                            expand=True,
                        )
                        entry_info = ft.Row(
                            controls=[
                                entry_video_thumbnail_img,
                                entry_about_info,
                                ft.Column(
                                    controls=[
                                        entry_download_icon,
                                        entry_delete_icon,
                                    ],
                                    alignment=ft.alignment.center,
                                ),
                            ],
                            alignment=ft.alignment.center,
                        )
                        entry_video_card = ft.Card(
                            key=key,
                            content=ft.Container(
                                content=ft.Column(
                                    controls=[
                                        entry_info,
                                        entry_progress_container,
                                    ],
                                    spacing=10,
                                ),
                                padding=4,
                            ),
                            margin=0,
                        )
                        self.cards[key] = entry_video_card
                        self.downloader.cards[key] = entry_video_card # こうすることで、DownloadクラスからCardの要素の操作ができる
                        self.added_urls.append(url)
                        self.card_container.controls.append(entry_video_card)
                        page.update()
                    else:
                        if not is_playlist:
                            video_title = ft.TextField(
                                label="タイトル",
                                value=data.get("title", "Unknown Title"),
                                adaptive=True,
                            )
                            video_date = ft.Text(
                                value=data.get("upload_date", "Unknown"),
                            )
                            video_uploader = ft.TextField(
                                label="投稿者",
                                value=data.get("uploader", "Unknown"),
                                adaptive=True,
                            )
                            thumbnail_img_src = data.get("thumbnail_path", None)
                            if not thumbnail_img_src:
                                # サムネイルがない場合は、compute_perfect_sizeでプレースホルダー画像を生成
                                placeholder = self.compute_perfect_size(page, 0, 0, key)
                                video_thumbnail_img = ft.Image(
                                    src=placeholder["src"],
                                    width=placeholder["width"],
                                    height=placeholder["height"],
                                    fit=ft.ImageFit.CONTAIN,
                                    border_radius=ft.border_radius.all(10),
                                )
                            else:
                                # 画像を読み込み、16:9の枠内に収まるように中央配置した背景画像を作成
                                with Image.open(thumbnail_img_src) as img:
                                    img_width, img_height = img.size
                                    perfect_img_size = self.compute_perfect_size(page, img_width, img_height, key)
                                    # 灰色の背景画像作成
                                    # リサイズはなし
                                    background = Image.new("RGB", (perfect_img_size["width"], perfect_img_size["height"]), (128, 128, 128))
                                    background.paste(img, (perfect_img_size["offset_x"], perfect_img_size["offset_y"]))
                                    # サムネイル画像配置枠
                                    frame_width = perfect_img_size["frame_width"]
                                    frame_height = perfect_img_size["frame_height"]
                                    # .temp内の一時ファイルに保存
                                    with tempfile.NamedTemporaryFile(delete=False, dir=self.temp_dir, suffix=".jpg") as temp_file:
                                        temp_path = temp_file.name
                                        background.save(temp_path, format="JPEG", quality=95) # JPG形式で保存
                                # 元のファイルをバックアップ
                                backup_path = thumbnail_img_src + ".bak"
                                os.rename(thumbnail_img_src, backup_path)
                                # 一時ファイルを元のファイルに置き換え
                                os.rename(temp_path, thumbnail_img_src)
                                # バックアップ削除(上書きが成功した場合)
                                os.remove(backup_path)
                                video_thumbnail_img = ft.Image(
                                    src=thumbnail_img_src,
                                    width=frame_width,
                                    height=frame_height,
                                    fit=ft.ImageFit.CONTAIN,
                                    border_radius=ft.border_radius.all(10),
                                )
                            # RadioGroupを作成
                            # 保存形式を個々に選択できるようにする(MovieとMusic)
                            rg = ft.RadioGroup(
                                value=settings.content_type,
                                content=ft.Row([
                                    ft.Radio(value="movie", label="Movie"),
                                    ft.Radio(value="music", label="Music"),
                                ]),
                            )
                            # lambda式の「遅延束縛」を回避するためにデフォルト引数としてkeyをバインドする
                            delete_icon = ft.IconButton(
                                icon=ft.Icons.DELETE_FOREVER_ROUNDED,
                                on_click=lambda e, key=key : self.remove_card(e, key, page, url),
                                tooltip="削除",
                            )
                            download_icon = ft.IconButton(
                                icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                                on_click=lambda e, key=key: self.download_video_by_key(e, key, page),
                                tooltip="ダウンロード",
                            )
                            progress = ft.ProgressBar(
                                visible=False,
                                value=None,
                            )
                            progress_container = ft.Container(
                                content=progress,
                                expand=True, # 親であるCardの幅いっぱいに広がるように
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                border_radius=ft.border_radius.all(8),
                            )
                            about_info = ft.Column(
                                controls=[
                                    video_title,
                                    ft.Row(
                                        controls=[
                                            video_uploader,
                                            ft.Row(
                                                controls=[
                                                    rg,
                                                    video_date,
                                                ],
                                                alignment=ft.MainAxisAlignment.END,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ],
                                expand=True,
                            )
                            info = ft.Row(
                                controls=[
                                    video_thumbnail_img,
                                    about_info,
                                    ft.Column(
                                        controls=[
                                            download_icon,
                                            delete_icon,
                                        ],
                                        alignment=ft.alignment.center,
                                    ),
                                ],
                                alignment=ft.alignment.center,
                            )
                            video_card = ft.Card(
                                key=key,
                                content=ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            info,
                                            progress_container,
                                        ],
                                        spacing=10,
                                    ),
                                    padding=4,
                                ),
                                margin=0,
                            )
                            self.cards[key] = video_card
                            self.downloader.cards[key] = video_card # こうすることで、DownloadクラスからCardの要素の操作ができる
                            self.added_urls.append(url)
                            self.card_container.controls.append(video_card)
                            page.update()
                        else:
                            # ここはプレイリストのリンクが入力されて、メタデータが正常に入手できなかった場合
                            playlist_title = ft.TextField(
                                label="プレイリスト名",
                                value="Unknown",
                                adaptive=True,
                            )
                            playlist_date = ft.Text(
                                value="Unknown",
                            )
                            playlist_uploader = ft.TextField(
                                label="投稿者",
                                value="Unknown",
                                adaptive=True,
                            )
                            placeholder_playlist = self.compute_perfect_size(page, 0, 0, key)
                            playlist_thumb_img = ft.Image(
                                src=placeholder_playlist["src"],
                                width=placeholder_playlist["width"],
                                height=placeholder_playlist["height"],
                                fit=ft.ImageFit.CONTAIN,
                                border_radius=ft.border_radius.all(10),
                            )
                            playlist_rg = ft.RadioGroup(
                                value=settings.content_type,
                                content=ft.Row([
                                    ft.Radio(value="movie", label="Movie"),
                                    ft.Radio(value="music", label="Music"),
                                ]),
                            )
                            # lambda式の「遅延束縛」を回避するためにデフォルト引数としてkeyをバインドする
                            playlist_delete_icon = ft.IconButton(
                                icon=ft.Icons.DELETE_FOREVER_ROUNDED,
                                on_click=lambda e, key=key: self.remove_card(e, key, page, url),
                                tooltip="削除",
                            )
                            playlist_download_icon = ft.IconButton(
                                icon=ft.Icons.CLOUD_DOWNLOAD_ROUNDED,
                                on_click=lambda e, key=key: self.download_video_by_key(e, key, page),
                                tooltip="ダウンロード",
                            )
                            playlist_progress = ft.ProgressBar(
                                visible=False,
                                value=None,
                            )
                            playlist_progress_container = ft.Container(
                                content=playlist_progress,
                                expand=True,
                                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                                border_radius=ft.border_radius.all(8),
                            )
                            playlist_about_info = ft.Column(
                                controls=[
                                    playlist_title,
                                    ft.Row(
                                        controls=[
                                            playlist_uploader,
                                            ft.Row(
                                                controls=[
                                                    playlist_rg,
                                                    playlist_date,
                                                ],
                                                alignment=ft.MainAxisAlignment.END,
                                            ),
                                        ],
                                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                                    ),
                                ],
                                expand=True,
                            )
                            playlist_info = ft.Row(
                                controls=[
                                    playlist_thumb_img,
                                    playlist_about_info,
                                    ft.Column(
                                        controls=[
                                            playlist_download_icon,
                                            playlist_delete_icon,
                                        ],
                                        alignment=ft.alignment.center,
                                    ),
                                ],
                                alignment=ft.alignment.center,
                            )
                            playlist_card = ft.Card(
                                key=key,
                                content=ft.Container(
                                    content=ft.Column(
                                        controls=[
                                            playlist_info,
                                            playlist_progress_container,
                                        ],
                                        spacing=10,
                                    ),
                                    padding=4,
                                ),
                                margin=0,
                            )
                            self.cards[key] = playlist_card
                            self.downloader.cards[key] = playlist_card # こうすることで、DownloadクラスからCardの要素の操作ができる
                            self.added_urls.append(url)
                            self.card_container.controls.append(playlist_card)
                            page.update()
            except Exception as ex:
                self.logger.error(
                    f"Error adding video card: {ex}",
                    exc_info=True
                )
                open_dlg(err_dlg, page)
            time.sleep(0.5) # 連続処理の負荷を軽減
    
    def handle_url_submit(self, e, tf, page):
        """
        テキストフィールドからURLを取得し、
        URL(存在確認と重複確認のチェックを抜けたもののみ)を追加し、条件変数を通知する
        """
        try:
            urls = tf.value.split("\n")
            if not urls:
                return
            tf.value = "" # add_video_cardは実行に時間がかかるため、先にクリアしておく
            page.update()
            # 各URLについて、前後の空白を削除する。
            # もし空白だけの場合は空文字列になるため、除外される。
            # また、既に追加済みのURLリスト（self.pre_url_list, self.added_urls）と重複していないかもチェック
            valid_urls = []
            for url in urls:
                trimmed_url = url.strip()  # 前後の空白を削除
                # trimmed_urlが空でなく、かつ重複していない場合にのみリストへ追加
                if trimmed_url and trimmed_url not in self.pre_url_list and trimmed_url not in self.added_urls and trimmed_url not in valid_urls:
                    valid_urls.append(trimmed_url)
            if valid_urls: # 追加するURLがある場合の処理
                with self.condition_pre:
                    self.pre_total_urls += len(valid_urls) # 追加するURLの数を追加
                    self.pre_url_list.extend(valid_urls) # URLをリスト末尾に追加
                    self.condition_pre.notify() # 待機中のスレッドを起こす
        except Exception as ex:
            self.logger.error(
                f"Error in handle_url_submit: {ex}",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ex
    
    def handle_window_resize(self, e, page):
        """
        ウィンドウサイズが変更された時に実行される関数
        """
        # 画面幅が変更された時の処理
        updated_width = int(page.window.width / 4)
        updated_height = int(updated_width * 9 / 16)
        for key, card in self.cards.items():
            info = card.content.content.controls[0]
            thumbnail_img = info.controls[0]
            thumbnail_img.width = updated_width
            thumbnail_img.height = updated_height
            page.update()
            self.logger.info(f"ウィンドウサイズが変更されました。 width: {updated_width}, height: {updated_height}")
    
    def download_video_by_key(self, e, key, page):
        """
        ダウンロードボタンが押されたカードの動画をダウンロードするコールバック関数
        """
        try:
            # ページ上から最新のCardを取得(保存していた参照ではなく、現在のコントロールツリーから)
            # dictであるcardsから参照
            target_card = self.cards[key]
            target_column = target_card.content.content
            target_info = target_column.controls[0]
            target_progress_bar = target_column.controls[1].content
            target_about_info = target_info.controls[1]
            target_title = target_about_info.controls[0]
            target_uploader = target_about_info.controls[1].controls[0]
            target_content_type = target_about_info.controls[1].controls[1].controls[0]
            json_path = os.path.join(self.temp_dir, f"{key}.json")
            # JSONファイルを読み込んで、更新
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not all(k in data for k in ("title", "uploader", "url")):
                self.logger.error(
                    "JSONファイルにtitleまたはuploaderまたはurlのキーがありません。",
                    exc_info=True
                )
                # sys.exit(1) # プログラムの終了
                raise ValueError("JSONファイルにtitleまたはuploaderまたはurlのキーが存在しません。")
            data["title"] = sanitize_filename(target_title.value)
            self.logger.debug(data["title"])
            data["uploader"] = target_uploader.value
            self.logger.debug(data["uploader"])
            data["content_type"] = target_content_type.value
            self.logger.debug(data["content_type"])
            # 更新したデータをJSONファイルに書き戻す
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.logger.info(f"{key}.jsonを更新しました")
            # ダウンロードボタンとデリートボタンを押せなくする
            download_button = target_info.controls[2].controls[0]
            delete_button = target_info.controls[2].controls[1]
            download_button.disabled = True  # ダウンロードボタンを無効化
            delete_button.disabled = True # デリートボタンを無効化
            target_title.disabled = True # タイトル入力欄を無効化
            target_content_type.disabled = True # ダウンロードタイプ選択無効化
            target_uploader.disabled = True # 投稿者テキストフィールド無効化
            # プログレスバーを見えるようにする
            target_progress_bar.visible = True # これでプログレスバーが見えるようになる(page.updateが必要)
            page.update() # ページ更新
            # ダウンロード処理開始
            self.downloader._check_content_type(key=key, page=page)
        except Exception as ex:
            self.logger.error(
                ex,
                exc_info=True
            )
            open_dlg(err_happen_dlg, page)
    
    def remove_card(self, e, key, page, url):
        try:
            if key in self.cards:
                page.controls.remove(self.cards[key])
                page.update()
                del self.cards[key]
                self.logger.info(f"self.cardsからkey: {key} を削除しました。")
                self.added_urls.remove(url)
                self.logger.info(f"self.added_urlsからurl: {url} を削除しました。")
            else:
                self.logger.error(
                    "keyの値が不正です",
                    exc_info=True
                )
                # sys.exit(1) # プログラムの終了
                raise KeyError("keyの値が不正です。")
        except Exception as ex:
            self.logger.error(
                ex,
                exc_info=True
            )
            open_dlg(delete_err_dlg, page)
    
    def import_text_files_result(self, e: ft.FilePickerResultEvent, tf, page):
        """読み込むURLが記入されたテキストファイルを読み込んで、検索欄に追加"""
        try:
            if e.files:
                file_paths = e.files
            if not e.files:
                self.logger.warning(
                    "ファイルが選択されませんでした。",
                    exc_info=True
                )
                return
            all_urls = [] # テキストファイルから読み取った全てのURLを格納するリスト
            for file_path in file_paths:
                with open(file_path, "r", encoding="utf-8") as file:
                    # ファイルの内容を行ごとに読み込み
                    urls = file.read().split("\n")
                    all_urls.extend(urls)
            # ここで習得したURLリスト(all_urls)の前後の空白を削除し、重複を取り除く
            valid_urls = []
            for url in all_urls:
                trimmed_url = url.strip()  # 前後の空白を削除
                # 空文字でなく、既に追加されていないURLのみを追加
                if trimmed_url and trimmed_url not in self.pre_url_list and trimmed_url not in self.added_urls and trimmed_url not in valid_urls:
                    valid_urls.append(trimmed_url)
            # 追加するURLが存在する場合、tf.valueにそれをセット(tf.valueの値をクリアしないように)
            if valid_urls:
                # 既存の内容がある場合は改行で区切って追加
                if tf.value:
                    tf.value += "\n" + "\n".join(valid_urls)
                else:
                    tf.value = "\n".join(valid_urls)
                page.update()
            else:
                self.logger.warning(
                    "選択されたファイルの内容が不正です",
                    exc_info=True
                )
                return
        except Exception as ex:
            self.logger.error(
                ex,
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ex
    
    def all_download(self, e, page):
        try:
            # 全ダウンロードボタンと全削除ボタンを使えなくする
            self.all_download_icon.disabled = True 
            self.all_delete_icon.disabled = True
            page.update()
            with ThreadPoolExecutor() as executor: # 同時並行的に処理
                futures = [executor.submit(self.download_video_by_key, None, key, page) for key in self.cards.keys()]
                self.logger.debug("全てのカードをそれぞれの形式でダウンロードする")
                # エラーをキャッチするために結果を取得
                for future in futures:
                    future.result()
        except Exception as ex:
            self.logger.error(
                ex,
                exc_info=True
            )
            error_occurred = True  # エラー発生フラグ
        else:
            error_occurred = False
        finally:
            # 全ての処理が完了した後に発火
            self.all_download_icon.disabled = False
            self.all_delete_icon.disabled = False
            page.update()
        if error_occurred:
            open_dlg(err_happen_dlg, page)
    
    def all_remove(self, e, page):
        try:
            # print("全てのカードを削除する") # デバッグ用
            for key, value in self.cards.items():
                page.controls.remove(value)
                del value
                page.update()
                self.logger.info(f"self.cardsからkey: {key} を削除しました。")
            self.added_urls = []
            self.logger.info("self.added_urlsを初期化しました")
        except Exception as ex:
            self.logger.error(
                ex,
                exc_info=True
            )
            open_dlg(delete_err_dlg, page)
    
    def go_to_setting_page(self, e, page: ft.Page):
        # 設定ページをviewsに追加して遷移
        page.views.append(self.settings_view(page))
        page.update()
    
    def go_to_logs_page(self, e, page: ft.Page):
        # ログページをviewsに追加して遷移
        page.views.append(self.logs_view(page))
        page.update()
    
    def logs_view(self, page: ft.Page) -> ft.View:
        def go_back_for_logs(e):
            page.views.pop()
            page.update()
        
        def get_directry_result(e: ft.FilePickerResultEvent):
            self.logger.info("ログファイル出力に挑戦します")
            try:
                # コピー先のファイル名作成
                log_file_name = os.path.basename(log_file)
                base, ext = os.path.splitext(log_file_name)
                log_file_copyname = f"{base}_copy{ext}"
                destination = e.path if e.path else None
                if destination:
                    destination_file = os.path.join(destination, log_file_copyname)
                    shutil.copy(log_file, destination_file)
                    self.logger.info(f"ファイルが保存されました: {destination_file}")
                else:
                    self.logger.info("ログファイル出力がキャンセルされました。")
            except Exception as ex:
                self.logger.error(f"ログファイル出力に失敗しました: {ex}")
                open_dlg(copy_err_dlg, page)
        get_directry_dialog = ft.FilePicker(on_result=get_directry_result)
        page.overlay.append(get_directry_dialog)
        
        def read_logfile():
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as ex:
                self.logger.error(
                    f"ログファイルの読み取りに失敗しました: {ex}",
                    exc_info=True
                )
                return f"ログファイルの読み取りに失敗しました: {ex}"
        
        log_content = read_logfile()
        log_column = ft.Column(
            controls=[
                ft.Text(
                    value=log_content,
                    selectable=True,
                )
            ],
        )
        
        # def scroll_to_end(e, page: ft.Page):
        #     log_column.scroll_to(offset=-1, duration=1000) # Columnを最後までスクロール
        #     page.update()
        
        logs_page = ft.View(
            route="/settings/logs",
            controls=[
                ft.AppBar(
                    title=ft.Text("ログ"),
                    leading=ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        on_click=go_back_for_logs,
                        tooltip="戻る"
                    ),
                    actions=[
                        ft.IconButton(
                            icon=ft.Icons.IOS_SHARE_ROUNDED,
                            on_click=lambda _: get_directry_dialog.get_directory_path(),
                            tooltip="ログファイル出力",
                            disabled=page.web
                        ),
                    ],
                    adaptive=True,
                    center_title=True
                ),
                log_column,
            ],
            scroll=ft.ScrollMode.ADAPTIVE
        )
        return logs_page
    
    def settings_view(self, page: ft.Page) -> ft.View:
        # 設定ページの戻るボタン押下時の処理
        def go_back(e):
            page.views.pop() # 現在のビュー(設定ページ)を削除
            page.theme_mode = getattr(ft.ThemeMode, settings.page_theme, None) # ページテーマをデフォルト値に戻す
            if not page.theme_mode:
                self.logger.error(
                    "page.theme_modeの値が不正です。",
                    exc_info=True
                )
                # sys.exit(1)
                raise ValueError("page.theme_modeの値が不正です。")
            page.update()
        
        # テーマ選択時の処理
        def change_theme(e):
            selected = e.control.value
            if selected == "Light":
                page.theme_mode = ft.ThemeMode.LIGHT
            elif selected == "Dark":
                page.theme_mode = ft.ThemeMode.DARK
            page.update()
        
        theme_dropdown = ft.Dropdown(
            label="テーマ選択",
            options=[
                ft.dropdown.Option("Light"),
                ft.dropdown.Option("Dark"),
            ],
            value="Light" if page.theme_mode == ft.ThemeMode.LIGHT else "Dark",
            on_change=change_theme,
            tooltip="テーマを切り替える",
            expand=True,
            width=page.window.width,
        )
        
        content_type_dropdown = ft.Dropdown(
            label="ダウンロードタイプ選択",
            options=[
                ft.dropdown.Option("Movie"),
                ft.dropdown.Option("Music"),
            ],
            value="Movie" if settings.content_type == "movie" else "Music",
            tooltip="ダウンロードタイプ切り替える",
            expand=True,
            width=page.window.width,
        )
        
        def get_change_save_dir_result(e: ft.FilePickerResultEvent):
            try:
                self.logger.info("ダウンロードフォルダーの変更を行います。")
                destination = e.path if e.path else None
                if destination:
                    save_dir.text = destination
                    self.logger.info(f"ダウンロード先が変更されました: {destination}")
                    page.update()
                else:
                    self.logger.info("ダウンロード先選択がキャンセルされました。")
            except Exception as ex:
                self.logger.error(f"ダウンロード先選択に失敗しました: {ex}")
                open_dlg(dl_err_dlg, page)
        
        get_change_save_dir_dialog = ft.FilePicker(on_result=get_change_save_dir_result)
        page.overlay.append(get_change_save_dir_dialog)
        
        save_dir = ft.TextButton(
            text=settings.download_dir,
            on_click=lambda _: get_change_save_dir_dialog.get_directory_path(),
            tooltip="ダウンロード先フォルダー",
        )
        
        def settings_save(e):
            try:
                self.logger.info("設定を更新します。")
                settings.update_setting("retry_chance", retry_chance_number.value)
                set_content_type = "movie" if content_type_dropdown.value == "Movie" else "music"
                settings.update_setting("content_type", set_content_type)
                set_theme_mode = "LIGHT" if theme_dropdown.value == "Light" else "DARK"
                settings.update_setting("page_theme", set_theme_mode)
                settings.update_setting("download_dir", save_dir.text)
                open_dlg(settings_save_dlg, page)
            except Exception as ex:
                self.logger.error(f"設定の更新に失敗しました: {ex}")
                open_dlg(save_err_dlg, page)
        
        settings_save_btn = ft.TextButton(
            "設定を保存する",
            icon=ft.Icons.SAVE_AS_ROUNDED,
            on_click=settings_save,
            expand=True,
            tooltip="設定を保存する"
        )
        
        def validate_number(e):
            # 入力が数字以外なら削除
            e.control.value = "".join(filter(str.isdigit, e.control.value))
            page.update()
        
        retry_chance_number = ft.TextField(
            label="リトライ回数",
            value=self.retries, 
            text_align=ft.TextAlign.CENTER,
            expand=True,
            on_change=validate_number,
            tooltip="リトライ回数",
        )
        
        def minus_click(e):
            retry_chance_number.value = str(int(retry_chance_number.value) - 1)
            page.update()
        
        def plus_click(e):
            retry_chance_number.value = str(int(retry_chance_number.value) + 1)
            page.update()
        
        settings_page = ft.View(
            route="/settings",
            controls=[
                ft.AppBar(
                    title=ft.Text("設定"),
                    leading=ft.IconButton(
                        icon=ft.Icons.ARROW_BACK,
                        on_click=go_back,
                        tooltip="戻る"
                    ),
                    actions=[(
                        ft.TextButton(
                            "ログ閲覧",
                            on_click=lambda e: self.go_to_logs_page(e, page),
                            tooltip="ログ閲覧",
                        )
                    )],
                    adaptive=True,
                    center_title=True
                ),
                ft.Container(
                    content=theme_dropdown,
                    alignment=ft.alignment.center,
                    expand=True,
                ),
                ft.Container(
                    content=content_type_dropdown,
                    alignment=ft.alignment.center,
                    expand=True,
                ),
                ft.Row(
                    controls=[
                        ft.IconButton(
                            ft.Icons.REMOVE,
                            on_click=minus_click,
                            tooltip="リトライ回数を一回減らします"
                        ),
                        retry_chance_number,
                        ft.IconButton(
                            ft.Icons.ADD,
                            on_click=plus_click,
                            tooltip="リトライ回数を一回増やします"
                        ),
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                ft.Container(
                    content=save_dir,
                    alignment=ft.alignment.center,
                ),
                ft.Container(
                    content=settings_save_btn,
                    alignment=ft.alignment.center,
                ),
            ],
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        return settings_page
    
    def main(self, page: ft.Page):
        """
        Fletのページを構築するメインメソッド
        """
        page.title = "YDownloader"
        
        # global宣言が必要
        global content_type_err_dlg, network_err_dlg, playlist_error_dlg, retry_error_dlg, link_err_dlg, err_dlg, err_happen_dlg, delete_err_dlg, save_err_dlg, copy_err_dlg, dl_err_dlg, settings_save_dlg
        content_type_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text("ダウンロードタイプの値が入手できませんでした。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, content_type_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        network_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text("ネットワーク接続を確認してください。"),
            actions=[
                ft.TextButton(
                    "閉じる", 
                    on_click=lambda e: close_dlg(e, network_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        playlist_error_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text("プレイリストダウンロード中にエラーが発生しました。"),
            actions=[
                ft.TextButton(
                    "閉じる", 
                    on_click=lambda e: close_dlg(e, playlist_error_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        retry_error_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text(f"{self.retries}回ダウンロードに失敗しました。"),
            actions=[
                ft.TextButton(
                    "閉じる", 
                    on_click=lambda e: close_dlg(e, retry_error_dlg, page),
                    tooltip="ダイアログを閉じます"
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        link_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text("入力されたリンクが正しくありません。"),
            actions=[
                ft.TextButton(
                    "閉じる", 
                    on_click=lambda e: close_dlg(e, link_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text(f"エラーが発生しました。"),
            actions=[
                ft.TextButton(
                    "閉じる", 
                    on_click=lambda e: close_dlg(e, err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        err_happen_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text("ダウンロードの途中でエラーが発生しました。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, err_happen_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        delete_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text("カード削除の途中でエラーが発生しました。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, delete_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        save_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text(f"設定の保存に失敗しました。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, save_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        copy_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text(f"ログファイルのコピーに失敗しました。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, copy_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        dl_err_dlg = ft.AlertDialog(
            title=ft.Text("エラー"),
            modal=True,
            content=ft.Text(f"ダウンロードフォルダーの選択に失敗しました。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, dl_err_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        settings_save_dlg = ft.AlertDialog(
            title=ft.Text("忠告"),
            modal=True,
            content=ft.Text(f"一部設定はアプリの次回起動以降反映されます。"),
            actions=[
                ft.TextButton(
                    "閉じる",
                    on_click=lambda e: close_dlg(e, settings_save_dlg, page),
                    tooltip="ダイアログを閉じます"
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        
        # ウィンドウのリサイズイベントを監視する(リサイズが完了したタイミングで実行されるようにする)
        page.on_resized = lambda e: self.handle_window_resize(e, page)
        # プログレスバーの作成(読み込みの進捗段階を表示する)
        progress_bar = ft.ProgressBar(
            value=(self.pre_current_urls / self.pre_total_urls) if self.pre_total_urls > 0 else 0
        )
        progress_bar_container = ft.Container(
            content=progress_bar,
            expand=True, # 親の幅いっぱいに広がるように
        )
        progress_text = ft.Text(value=f"{self.pre_current_urls}/{self.pre_total_urls}")
        progress = ft.Row(
            controls=[
                progress_bar_container,
                progress_text,
            ],
            visible=False,
            expand=True,
        )
        # ここでprogress.visibleとしてしまうと、インスタンス化できないので、ページの繁栄ができない
        self.progress = progress # これでprogressのvisibleを操作する
        # フォントの読み込み
        font_dir = os.path.join(os.path.dirname(get_script_dir()), "src", "assets", "fonts", "ZenOldMincho")
        page.fonts = {
            "ZenOldMincho-Black": os.path.join(font_dir, "ZenOldMincho-Black.ttf"),
            "ZenOldMincho-Bold": os.path.join(font_dir, "ZenOldMincho-Bold.ttf"),
            "ZenOldMincho-SemiBold": os.path.join(font_dir, "ZenOldMincho-SemiBold.ttf"),
            "ZenOldMincho-Medium": os.path.join(font_dir, "ZenOldMincho-Medium.ttf"),
            "ZenOldMincho-Regular": os.path.join(font_dir, "ZenOldMincho-Regular.ttf")
        } # 上の方が字が太い
        # アプリ全体のデフォルトフォントとして、"ZenOldMincho-Regular"を設定(ユーザーが変えられるようにする)
        page.theme = ft.Theme(font_family="ZenOldMincho-SemiBold")
        
        t = ft.Text(
            value="YDownloader",
            size=30,
        )
        tt = ft.Container(
            content=t,
            alignment=ft.alignment.center,
        )
        
        # 設定ボタン(歯車アイコン)
        # 押すと設定ページに遷移できるようにする
        setting_button = ft.IconButton(
            icon=ft.Icons.SETTINGS_ROUNDED,
            on_click=lambda e: self.go_to_setting_page(e, page),
            tooltip="設定を開く",
        )
        # stackを使用して、歯車アイコンを他のレイアウトに影響を与えることなく右上に配置する
        stack = ft.Stack(
            controls=[
                tt, # 下層のレイアウト
                setting_button, # このボタンが上に重ねられる
            ],
            alignment=ft.alignment.top_right,
        )
        
        # 動的にCardを追加するためのコンテナ
        self.card_container = ft.Column(
            controls=[],
            expand=True,
        )
        
        tf = ft.TextField(
            label="URL",
            value="",
            expand=True, # こうすることで、虫眼鏡アイコンとの配置が最適なものになる
            adaptive=True, # iOS向けに適切なデザインになる
            autofocus=True, # 最初にURL入力欄がフォーカスされる
            multiline=True, # 複数行入力可能にする
            max_lines=2,
            shift_enter=True, # Shift+Enterで改行できるようにする
            on_submit=lambda e: self.handle_url_submit(e, tf, page), # Enter(Shiftなし)で送信する処理
        )
        # 検索アイコンのボタン
        sb = ft.IconButton(
            icon=ft.Icons.SEARCH_ROUNDED,
            on_click=lambda e: self.handle_url_submit(e, tf, page),
            tooltip="検索"
        )
        # import_text_filesを呼び出す前にファイルピッカーを作成して、page.overlayに追加
        file_picker_dialog = ft.FilePicker(on_result=lambda e: self.import_text_files_result(e, tf, page))
        page.overlay.append(file_picker_dialog)
        # テキストファイル取り込みボタン
        ib = ft.IconButton(
            icon=ft.Icons.DOWNLOAD_ROUNDED,
            on_click=lambda _: file_picker_dialog.pick_files(
                allow_multiple=True,
                file_type=ft.FilePickerFileType.CUSTOM,
                allowed_extensions=["txt"] # txtファイルのみ選択可能にする
            ),
            tooltip="テキストファイル取り込み",
        )
        all_download_icon = ft.IconButton(
            icon=ft.Icons.CLOUD_DOWNLOAD_OUTLINED,
            on_click=lambda e: self.all_download(e, page),
            tooltip="すべてをダウンロード",
        )
        self.all_download_icon = all_download_icon
        all_delete_icon = ft.IconButton(
            icon=ft.Icons.DELETE_FOREVER,
            on_click=lambda e: self.all_remove(e, page),
            tooltip="すべてを削除",
        )
        self.all_delete_icon = all_delete_icon
        
        # デフォルトのページテーマを読み込む
        # ft.ThemeMode.LIGHTまたはft.ThemeMode.DARKが定義される
        page.theme_mode = getattr(ft.ThemeMode, settings.page_theme, None)
        if not page.theme_mode:
            self.logger.error(
                "page.theme_modeの値が不正です。",
                exc_info=True
            )
            # sys.exit(1) # プログラムの終了
            raise ValueError("page.theme_modeの値が不正です。")
        
        # メインページのレイアウトをViewにまとめる
        main_view = ft.View(
            route="/",
            controls=[
                stack,
                ft.Card(
                    content=ft.Container(
                        content=ft.Row(
                            controls=[
                                tf,
                                sb,
                            ], spacing=20,
                        ), padding=10,
                    ), margin=5,
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            progress,
                            ib,
                            all_download_icon,
                            all_delete_icon,
                        ],
                        spacing=20,
                        alignment=ft.MainAxisAlignment.END,
                    ), padding=10,
                ),
                # ここにvideo_cardを動的に追加する
                self.card_container, 
            ],
            scroll=ft.ScrollMode.ADAPTIVE,
        )
        
        page.views.append(main_view)
        page.update()
        
        # URL監視スレッドの起動
        processing_thread = threading.Thread(
            target=self.add_video_card,
            args=(page,),
            daemon=True,
        )
        processing_thread.start()


try:
    setup_logging()
    # externalディレクトリのパスを取得
    EXTERNAL_PATH = get_external_path(app_name="YDownloader")
    if not os.path.exists(EXTERNAL_PATH):
        logger = logging.getLogger()
        logger.error(
            "externalフォルダーが存在しません。インストールし直してください。",
            exc_info=True
        )
        # sys.exit(1) # プログラムの終了
        raise FileNotFoundError("externalフォルダーが存在しません。")
    settings = DefaultSettingsLoader()
    downloader = Download(settings)
    app = YDownloader(settings, downloader)
    ft.app(target=app.main)
except Exception as ex:
    raise ex