import requests
from bs4 import BeautifulSoup
# import threading # ❌ 병렬 처리 제거
from collections import defaultdict
import datetime
import json
import time
import os

# Flask 임포트
from flask import Flask, jsonify, render_template

# Selenium 관련 라이브러리 임포트
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, TimeoutException as SelTimeoutException

# =========================================================================
# 0. 설정 및 초기화
# =========================================================================

# Flask 애플리케이션 초기화
app = Flask(__name__)

def initialize_selenium_driver():
    options = Options()
    
    # 🌟 1. 필수 옵션: Render 환경에서 실행하기 위해 필요
    options.add_argument("--headless")              # GUI 없이 실행
    options.add_argument("--no-sandbox")            # 보안 문제 회피
    options.add_argument("--disable-dev-shm-usage")  # 메모리 문제 해결
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    
    # 🌟 2. Render에서 사용하는 Chromium 경로 설정
    # Render는 'CHROME_PATH' 환경 변수를 제공하지 않으므로, 
    # 일반적인 경로 또는 Binary 파일을 사용하도록 시도해야 합니다.
    # Heroku의 Buildpack과 유사하게, Render도 Chromium을 제공하는 Buildpack이 필요하거나,
    # 아래와 같이 OS 환경에 따라 동적으로 경로를 설정해야 합니다.

    # ❗주의: 이 코드는 'get_kbs_selenium_url' 등 Selenium을 사용하는 모든 함수 내부에 적용되어야 합니다.
    # Render 환경에서 Chromium 바이너리 경로를 OS 환경 변수에서 가져오거나 추정합니다.
    # 만약 get_kbs_selenium_url 내부에서 WebDriverException이 발생한다면 이 경로 설정이 잘못된 것입니다.
    
    try:
        # Render/Heroku 환경에 맞는 경로 설정 시도 (환경 변수 또는 추정 경로)
        # Heroku Buildpack을 사용하는 경우의 환경 변수 이름과 유사할 수 있음.
        # Render에서 명확한 환경 변수를 제공하지 않는 경우, 아래의 설정이 필요합니다.
        
        # 대부분의 PaaS 환경에서 실행 가능한 방법:
        driver = webdriver.Chrome(options=options) 
    except WebDriverException:
        # 기본 경로에서 실패할 경우, 다른 경로를 시도하거나 'webdriver-manager'를 사용합니다.
        # Render에서 명시적인 Chromium 경로를 제공받지 못하면, 
        # 이 단계에서 오류가 발생할 가능성이 높습니다.
        print(">> WebDriver 초기화 실패. Render 환경의 추가 설정이 필요할 수 있습니다.")
        raise
        
    return driver

# --- 1. CHANNEL_URLS (KBS3R, KBS한민족 최종 이름 반영) ---
CHANNEL_URLS = {
    'KBS클래식FM': 'KBS_SELENIUM', 'KBS1R': 'KBS_SELENIUM', 'KBS쿨FM': 'KBS_SELENIUM',
    'KBS해피FM': 'KBS_SELENIUM', 'KBS3R': 'KBS_SELENIUM', 'KBS한민족': 'KBS_SELENIUM',
    'KBSWorldRadio': 'KBS_SELENIUM',

    'MBCFM4U': 'MBC_DYNAMIC', 'MBC표준FM': 'MBC_DYNAMIC',
    'SBS파워FM': 'SBS_DYNAMIC', 'SBS러브FM': 'SBS_DYNAMIC',

    'BBS불교방송': 'BBS_DYNAMIC', 'EBS교육방송': 'EBS_DYNAMIC', 'CPBC 평화방송': 'CPBC_DYNAMIC',

    # 업데이트된 고정 URL (8개)
    'CBS음악FM': 'https://m-aac.cbs.co.kr/mweb_cbs939/_definst_/cbs939.stream/playlist.m3u8',
    'CBS표준FM': 'https://m-aac.cbs.co.kr/mweb_cbs981/_definst_/cbs981.stream/playlist.m3u8',
    'TBS교통방송': 'https://cdnfm.tbs.seoul.kr/tbs/_definst_/tbs_fm_web_360.smil/playlist.m3u8',
    '경인방송': 'https://stream.ifm.kr/live/aod1/chunklist_0_audio_5097359403294618776_llhls.m3u8',
    'YTN NEWS FM': 'https://radiolive.ytn.co.kr/radio/_definst_/20211118_fmlive/playlist.m3u8',
    '극동방송': 'https://mlive3.febc.net/live5/seoulfm/playlist.m3u8',
    '국악방송': 'https://mgugaklive.nowcdn.co.kr/gugakradio/gugakradio.stream/playlist.m3u8',
    '원음방송': 'https://wbsradio.kr/wbs-seoul',
}

# 동적 URL 결과를 캐시할 전역 변수
STREAM_URL_CACHE = {}
CACHE_LAST_UPDATED = None
CACHE_EXPIRATION_SECONDS = 3600 # 1시간마다 업데이트

# =========================================================================
# 1.5 동적 스트림 URL 추출 함수 (Selenium 포함)
# -------------------------------------------------------------------------
# get_dynamic_stream_url_selenium, get_mbc_stream_url, get_sbs_stream_url, 
# get_kbs_selenium_url, get_other_dynamic_url 함수들은 로직이 길어 생략하며, 
# **기존 코드 그대로 유지합니다.**
# =========================================================================

# --- 1.6 모든 동적 URL을 가져오는 함수 (순차 처리로 변경됨) ---
def fetch_all_dynamic_urls():
    global STREAM_URL_CACHE, CACHE_LAST_UPDATED
    
    # 💡 이 함수는 is_cache_valid() 검사를 통과했을 때만 호출됩니다.
    
    print(">> 동적 URL 캐시 만료. 새롭게 추출 시작 (순차 처리).")
    new_cache = {}
    
    channels_to_fetch = [name for name, link in CHANNEL_URLS.items() if link.endswith('_DYNAMIC') or link.endswith('_SELENIUM')]
    
    results = {}
    
    # ❌ 스레딩 제거: 순차적으로 처리합니다.
    for channel_name in channels_to_fetch:
        print(f"   [Processing] {channel_name}...")
        link_type = CHANNEL_URLS[channel_name]
        url = None
        
        # 해당 채널에 맞는 추출 함수 호출
        if link_type == 'MBC_DYNAMIC': url = get_mbc_stream_url(channel_name)
        elif link_type == 'SBS_DYNAMIC': url = get_sbs_stream_url(channel_name)
        elif link_type == 'KBS_SELENIUM': url = get_kbs_selenium_url(channel_name)
        elif link_type in ('BBS_DYNAMIC', 'EBS_DYNAMIC', 'CPBC_DYNAMIC'): url = get_other_dynamic_url(channel_name)
        
        # 결과 저장
        results[channel_name] = url if url else "URL_NOT_FOUND"
        
        # 💡 각 채널 추출 후 1초 대기 (선택 사항이지만 메모리 정리를 위해 권장)
        time.sleep(1) 
        
    new_cache = results
    
    # 고정 URL 캐시에 추가
    for name, link in CHANNEL_URLS.items():
        if not (link.endswith('_DYNAMIC') or link.endswith('_SELENIUM')):
            new_cache[name] = link
            
    STREAM_URL_CACHE = new_cache
    CACHE_LAST_UPDATED = datetime.datetime.now()
    
    print(f">> 동적 URL 추출 완료 (순차). 총 {len(new_cache)}개 채널 URL 업데이트됨.")
    return STREAM_URL_CACHE

# -------------------------------------------------------------------------

# --- 1.7 캐시 유효성 검사 함수 추가 ---
def is_cache_valid():
    """캐시된 데이터가 유효 시간(1시간) 이내인지 확인합니다."""
    global CACHE_LAST_UPDATED
    
    if CACHE_LAST_UPDATED is None:
        return False
        
    now = datetime.datetime.now()
    if (now - CACHE_LAST_UPDATED).total_seconds() < CACHE_EXPIRATION_SECONDS:
        return True
    return False

# -------------------------------------------------------------------------
# 2. 네이버 편성표 데이터 수집 함수 (기존 코드 그대로 유지)
# -------------------------------------------------------------------------
def get_naver_radio_schedule():
    # ... (기존 get_naver_radio_schedule 함수 로직)
    naver_url = 'https://search.naver.com/search.naver?query=%EB%9D%BC%EB%94%94%EC%98%A4+%ED%8E%B8%EC%84%B1%ED%91%9C'
    # ... (중략) ...
    try:
        # ... (중략) ...
        final_channel_list = renamed_channel_names
        return final_channel_list, timetable_data
    except Exception as e:
        print(f"편성표 수집 오류: {e}")
        return [], {}

# =========================================================================
# 3. 데이터 처리 및 Flask API 엔드포인트
# =========================================================================

# -------------------------------------------------------------------------
# process_schedule_data 함수 내부에 변경 필요
# -------------------------------------------------------------------------
def process_schedule_data(channel_names, timetable_data):
    # ... (기존 process_schedule_data 함수 로직 유지) ...
    # ... (중략) ...

    # 동적/고정 URL 캐시 데이터를 가져옵니다.
    # 💡 이 함수 호출 시, STREAM_URL_CACHE에는 이미 최신(혹은 캐시된) 데이터가 들어 있어야 합니다.
    cached_urls = STREAM_URL_CACHE # fetch_all_dynamic_urls() 호출 대신 전역 변수 직접 사용
    
    for channel in ordered_channels:
        # ... (중략) ...
        final_output['schedule'].append({
            "channel_name": channel,
            "stream_url": cached_urls.get(channel, "URL_PROCESSING_ERROR"), # 캐시된 URL 포함
            "programs": channel_schedule
        })
        
    return final_output


@app.route('/')
def home():
    """프론트엔드 템플릿을 렌더링하고 서버 상태를 확인합니다."""

    # 💡 캐시 유효성 검사 (home 경로에서는 캐시가 유효하지 않아도 구동을 강제합니다.)
    if CACHE_LAST_UPDATED is None or not is_cache_valid():
        try:
            # 최초 로딩 시 강제 업데이트 시도 (순차 처리)
            fetch_all_dynamic_urls()
        except Exception as e:
            print(f"Initial URL fetch failed: {e}")

    timestamp_str = CACHE_LAST_UPDATED.strftime('%Y-%m-%d %H:%M:%S') if CACHE_LAST_UPDATED else "N/A"

    # templates/index.html 파일을 렌더링합니다.
    return render_template('index.html', timestamp=timestamp_str)

@app.route('/schedule')
def get_schedule_api():
    """편성표 데이터와 스트림 URL을 JSON으로 반환하는 API 엔드포인트입니다."""
    
    # 1. 편성표 데이터 수집
    channel_names, timetable_data = get_naver_radio_schedule()
    
    if not channel_names:
        return jsonify({"error": "Failed to fetch schedule data from Naver."}), 500
        
    # 2. 💡 캐시 유효성 검사 및 동적 URL 추출/캐시 (Selenium 방어 로직)
    global STREAM_URL_CACHE
    
    if is_cache_valid():
        print(">> 캐시 유효함. Selenium 구동 생략.")
        # 캐시가 유효하면 기존 캐시된 URL 사용 (STREAM_URL_CACHE는 이미 업데이트되어 있음)
    else:
        print(">> 캐시 만료 또는 없음. Selenium 구동 시작.")
        # 캐시가 만료되었을 때만 무거운 Selenium 구동 함수 호출
        try:
            fetch_all_dynamic_urls() # 순차적으로 구동되며, STREAM_URL_CACHE를 업데이트함
        except Exception as e:
            print(f"❌ 동적 URL 추출 중 오류 발생: {e}")
            # 오류 발생 시 기존 캐시(만료된 데이터)를 사용하거나, 빈 딕셔너리를 사용하여 서비스 중단 방지
            if not STREAM_URL_CACHE:
                STREAM_URL_CACHE = {name: CHANNEL_URLS[name] for name in CHANNEL_URLS if not (CHANNEL_URLS[name].endswith('_DYNAMIC') or CHANNEL_URLS[name].endswith('_SELENIUM'))}
            
    # 3. 데이터 처리 및 JSON 응답 반환
    final_json_data = process_schedule_data(channel_names, timetable_data)
    
    return jsonify(final_json_data)

# =========================================================================
# 4. 메인 실행 (기존 코드 그대로 유지) -> gunicorn 사용을 위해 제거하거나 수정
# =========================================================================
if __name__ == '__main__':
    # Render 환경에서 포트 자동 설정
    port = int(os.environ.get("PORT", 5000))
    # Render 환경에서는 0.0.0.0 바인딩이 필수
    app.run(host='0.0.0.0', port=port, debug=False) 
# 이 부분을 제거하고 Procfile의 gunicorn 명령에 맡깁니다.

