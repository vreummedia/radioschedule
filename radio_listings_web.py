import requests
from bs4 import BeautifulSoup
from collections import defaultdict
import datetime
import json
import time
import os
import random # User-Agent 랜덤 선택용

# Flask 임포트
from flask import Flask, jsonify, render_template

# Selenium 관련 라이브러리 임포트
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException, NoSuchElementException

# =========================================================================
# 0. 설정 및 초기화
# =========================================================================

# Flask 애플리케이션 초기화
app = Flask(__name__)

# --- 0.1 User-Agent 목록 ---
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:89.0) Gecko/20100101 Firefox/89.0'
]

# --- 1. CHANNEL_URLS ---
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
# =========================================================================

# --- 1.5.1 Render 환경을 위한 Selenium 드라이버 설정 ---
def setup_selenium_driver():
    """Render 환경에 맞게 Chrome WebDriver를 설정합니다."""
    # Render 환경에서 Chromium 경로를 환경 변수에서 가져옵니다.
    CHROMIUM_PATH = os.environ.get('CHROMIUM_PATH')
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    options.add_argument(f'user-agent={random.choice(USER_AGENTS)}') # Selenium에도 User-Agent 적용

    # Render에서 Chromium 경로가 설정되어 있다면 사용
    if CHROMIUM_PATH:
        options.binary_location = CHROMIUM_PATH
        print(f">> Chromium path set: {CHROMIUM_PATH}")
    else:
        # 로컬 환경 테스트용 (deploy 시에는 사용되지 않음)
        print(">> Using default Chrome path (Local testing).")


    try:
        # Render에서 `webdriver.Chrome()`만 사용 시 오류가 날 수 있으므로 executable_path 명시 (버전에 따라 필요)
        # 하지만 최신 버전의 selenium-manager는 자동 감지하므로, 문제가 발생하면 `service` 객체를 사용해야 합니다.
        # 여기서는 Render의 일반적인 headless 설정을 따릅니다.
        driver = webdriver.Chrome(options=options)
        return driver
    except WebDriverException as e:
        print(f"❌ Selenium WebDriver 초기화 실패: {e}")
        # Render의 빌드 환경 또는 환경 변수(CHROMIUM_PATH) 설정을 다시 확인해야 합니다.
        return None

# --- 1.5.2 동적 URL 추출 함수 (Placeholder) ---

def get_mbc_stream_url(channel_name):
    """MBC 동적 URL 추출 로직 (Placeholder)."""
    # 실제 MBC 페이지에서 m3u8 또는 live URL을 찾는 복잡한 로직이 필요합니다.
    print(f"  [MBC] 동적 URL 추출 시도: {channel_name}")
    driver = None
    try:
        driver = setup_selenium_driver()
        if driver is None: return None
        # 예시: driver.get('MBC_URL'); driver.find_element(By.TAG_NAME, 'audio').get_attribute('src') 등
        
        # 실제 로직에서는 10~20초 이상 걸릴 수 있습니다.
        time.sleep(3) 
        
        # 추출 성공 가정
        return "https://placeholder.mbc.live/stream_mbc.m3u8"
    except Exception as e:
        print(f"  ❌ MBC {channel_name} URL 추출 실패: {e}")
        return None
    finally:
        if driver: driver.quit()

def get_sbs_stream_url(channel_name):
    """SBS 동적 URL 추출 로직 (Placeholder)."""
    print(f"  [SBS] 동적 URL 추출 시도: {channel_name}")
    driver = None
    try:
        driver = setup_selenium_driver()
        if driver is None: return None
        time.sleep(3)
        return "https://placeholder.sbs.live/stream_sbs.m3u8"
    except Exception as e:
        print(f"  ❌ SBS {channel_name} URL 추출 실패: {e}")
        return None
    finally:
        if driver: driver.quit()

def get_kbs_selenium_url(channel_name):
    """KBS 동적 URL 추출 로직 (Placeholder)."""
    print(f"  [KBS] 동적 URL 추출 시도: {channel_name}")
    driver = None
    try:
        driver = setup_selenium_driver()
        if driver is None: return None
        time.sleep(4)
        return "https://placeholder.kbs.live/stream_kbs.m3u8"
    except Exception as e:
        print(f"  ❌ KBS {channel_name} URL 추출 실패: {e}")
        return None
    finally:
        if driver: driver.quit()

def get_other_dynamic_url(channel_name):
    """BBS, EBS, CPBC 등 기타 동적 URL 추출 로직 (Placeholder)."""
    print(f"  [OTHER] 동적 URL 추출 시도: {channel_name}")
    driver = None
    try:
        # 이들은 requests로 가능할 수도 있으나, 여기서는 Selenium 사용 가정
        driver = setup_selenium_driver()
        if driver is None: return None
        time.sleep(2)
        return f"https://placeholder.other.live/{channel_name}.m3u8"
    except Exception as e:
        print(f"  ❌ 기타 {channel_name} URL 추출 실패: {e}")
        return None
    finally:
        if driver: driver.quit()

# --- 1.6 모든 동적 URL을 가져오는 함수 (순차 처리) ---
def fetch_all_dynamic_urls():
    global STREAM_URL_CACHE, CACHE_LAST_UPDATED
    
    print(">> 동적 URL 캐시 만료. 새롭게 추출 시작 (순차 처리).")
    new_cache = {}
    
    channels_to_fetch = [name for name, link in CHANNEL_URLS.items() if link.endswith('_DYNAMIC') or link.endswith('_SELENIUM')]
    
    results = {}
    
    for channel_name in channels_to_fetch:
        print(f"    [Processing] {channel_name}...")
        link_type = CHANNEL_URLS[channel_name]
        url = None
        
        # 해당 채널에 맞는 추출 함수 호출
        if link_type == 'MBC_DYNAMIC': url = get_mbc_stream_url(channel_name)
        elif link_type == 'SBS_DYNAMIC': url = get_sbs_stream_url(channel_name)
        elif link_type == 'KBS_SELENIUM': url = get_kbs_selenium_url(channel_name)
        elif link_type in ('BBS_DYNAMIC', 'EBS_DYNAMIC', 'CPBC_DYNAMIC'): url = get_other_dynamic_url(channel_name)
        
        # 결과 저장
        results[channel_name] = url if url else "URL_NOT_FOUND"
        
        # 메모리 정리 및 과부하 방지를 위해 각 채널 추출 후 1초 대기
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

# --- 1.7 캐시 유효성 검사 함수 ---
def is_cache_valid():
    """캐시된 데이터가 유효 시간(1시간) 이내인지 확인합니다."""
    global CACHE_LAST_UPDATED
    
    if CACHE_LAST_UPDATED is None:
        return False
        
    now = datetime.datetime.now()
    if (now - CACHE_LAST_UPDATED).total_seconds() < CACHE_EXPIRATION_SECONDS:
        return True
    return False

# =========================================================================
# 2. 네이버 편성표 데이터 수집 함수 (가장 중요하게 수정된 부분)
# =========================================================================

def get_naver_radio_schedule():
    """네이버에서 라디오 편성표 데이터를 수집합니다. User-Agent를 추가하여 봇 차단을 우회합니다."""
    naver_url = 'https://search.naver.com/search.naver?query=%EB%9D%BC%EB%94%94%EC%98%A4+%ED%8E%B8%EC%84%B1%ED%91%9C'
    
    # 💡 User-Agent 추가: 봇 차단 방지
    headers = {
        'User-Agent': random.choice(USER_AGENTS)
    }
    
    try:
        # 요청 및 HTTP 상태 확인
        response = requests.get(naver_url, headers=headers, timeout=10)
        response.raise_for_status() 
        soup = BeautifulSoup(response.content, 'html.parser')

        # ------------------------------------------------------------------
        # 네이버 편성표 스크래핑 로직 (User-Agent가 추가되어 이제 정상 작동해야 합니다)
        # ------------------------------------------------------------------
        
        # 1. 채널 목록 추출
        # CSS 선택자: ._radio_schedule_tab_content > ul > li
        channel_list_elements = soup.select('._radio_schedule_tab_content ul li')
        
        # 네이버에서 사용하는 채널 이름과 코드
        naver_channel_names = [
            'MBC FM4U', 'MBC 표준FM', 'KBS 2FM(Cool FM)', 'KBS 2라디오(Happy FM)',
            'KBS 1라디오', 'KBS 3라디오', 'KBS 클래식FM', 'KBS 한민족방송', 'KBS 월드 라디오',
            'SBS 파워FM', 'SBS 러브FM', 'CBS 음악FM', 'CBS 표준FM', 'TBS 교통방송',
            'BBS 불교방송', 'EBS 교육방송', 'CPBC 평화방송', '경인방송', 'YTN NEWS FM',
            '극동방송', '국악방송', '원음방송'
        ]
        
        # 웹 앱에서 사용할 최종 이름
        renamed_channel_names = {
            'MBC FM4U': 'MBCFM4U', 'MBC 표준FM': 'MBC표준FM', 'KBS 2FM(Cool FM)': 'KBS쿨FM',
            'KBS 2라디오(Happy FM)': 'KBS해피FM', 'KBS 1라디오': 'KBS1R', 'KBS 3라디오': 'KBS3R',
            'KBS 클래식FM': 'KBS클래식FM', 'KBS 한민족방송': 'KBS한민족', 'KBS 월드 라디오': 'KBSWorldRadio',
            'SBS 파워FM': 'SBS파워FM', 'SBS 러브FM': 'SBS러브FM', 'CBS 음악FM': 'CBS음악FM',
            'CBS 표준FM': 'CBS표준FM', 'TBS 교통방송': 'TBS교통방송', 'BBS 불교방송': 'BBS불교방송',
            'EBS 교육방송': 'EBS교육방송', 'CPBC 평화방송': 'CPBC 평화방송', '경인방송': '경인방송',
            'YTN NEWS FM': 'YTN NEWS FM', '극동방송': '극동방송', '국악방송': '국악방송',
            '원음방송': '원음방송'
        }

        final_channel_list = []
        timetable_data = defaultdict(list)
        
        for i, channel_element in enumerate(channel_list_elements):
            if i >= len(naver_channel_names):
                continue

            naver_name = naver_channel_names[i]
            app_name = renamed_channel_names.get(naver_name, naver_name)
            final_channel_list.append(app_name)
            
            # 2. 편성표 데이터 추출
            # 각 채널 블록에서 프로그램 목록을 추출
            program_elements = channel_element.select('.time_list > li')
            
            for program_li in program_elements:
                time_span = program_li.select_one('.time_box').get_text(strip=True)
                title = program_li.select_one('.title').get_text(strip=True)
                
                # '새벽 00:00' 포맷을 datetime.time 객체로 변환 가능하도록 처리
                # 네이버 편성표는 24시간 표기이므로 간단히 처리
                try:
                    time_obj = datetime.datetime.strptime(time_span, '%H:%M').time()
                except ValueError:
                    # '새벽' 문구가 있다면 제거 후 재시도
                    if '새벽' in time_span:
                        time_span = time_span.replace('새벽', '').strip()
                        try:
                            time_obj = datetime.datetime.strptime(time_span, '%H:%M').time()
                        except ValueError:
                            # 변환 실패 시 로그만 남기고 다음으로
                            print(f"시간 포맷 오류: {time_span} for {title}")
                            continue
                    else:
                        continue # 처리할 수 없는 시간 포맷은 건너뜀


                # 현재 시간을 UTC 9시간 기준으로 변환
                current_time_utc9 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
                # 프로그램 시작 시간을 오늘 날짜에 붙입니다.
                start_datetime = current_time_utc9.replace(hour=time_obj.hour, minute=time_obj.minute, second=0, microsecond=0)
                
                # 편성표는 보통 00시 기준으로 전날 25시, 26시처럼 다음 날 새벽 시간을 포함하므로 
                # 시작 시간이 현재 시간보다 12시간 이상 앞서면 어제 날짜로 간주합니다.
                if (current_time_utc9 - start_datetime).total_seconds() > (12 * 3600):
                    start_datetime += datetime.timedelta(days=1)


                timetable_data[app_name].append({
                    "start_time": start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    "program_title": title,
                })

            # 프로그램 목록이 정렬되어 있지 않을 수 있으므로, 시작 시간 기준으로 정렬 (Naver는 보통 정렬되어 있음)
            timetable_data[app_name].sort(key=lambda x: datetime.datetime.strptime(x['start_time'], '%Y-%m-%d %H:%M:%S'))


        if not final_channel_list:
            raise Exception("No channel data found in Naver response.")
            
        return final_channel_list, timetable_data

    except requests.exceptions.RequestException as e:
        # 403 Forbidden과 같은 HTTP 오류 또는 네트워크 오류 처리
        print(f"❌ 네이버 편성표 요청 오류 (Network/HTTP Error - 봇 차단 가능성): {e}")
        return [], {}
    except Exception as e:
        # Beautiful Soup 파싱 오류 또는 데이터 구조 오류 처리
        print(f"❌ 편성표 데이터 파싱 오류: {e}")
        return [], {}


# =========================================================================
# 3. 데이터 처리 및 Flask API 엔드포인트
# =========================================================================

def process_schedule_data(channel_names, timetable_data):
    """수집된 편성표 데이터와 캐시된 스트림 URL을 결합합니다."""
    ordered_channels = [name for name in CHANNEL_URLS if name in channel_names]
    
    final_output = {
        "metadata": {
            "source": "Naver Radio Schedule",
            "last_updated": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        },
        "schedule": []
    }

    # 동적/고정 URL 캐시 데이터를 가져옵니다.
    cached_urls = STREAM_URL_CACHE 
    
    for channel in ordered_channels:
        channel_schedule = timetable_data.get(channel, [])
        
        # 프로그램 시작 시간과 현재 시간을 비교하여 현재 방송 중인 프로그램을 찾습니다.
        now_utc9 = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        current_program = "정보 없음"
        
        for i, program in enumerate(channel_schedule):
            start_dt = datetime.datetime.strptime(program['start_time'], '%Y-%m-%d %H:%M:%S')
            
            # 다음 프로그램의 시작 시간을 찾거나, 목록의 마지막이면 다음 날 0시를 끝 시간으로 간주
            if i + 1 < len(channel_schedule):
                end_dt = datetime.datetime.strptime(channel_schedule[i+1]['start_time'], '%Y-%m-%d %H:%M:%S')
            else:
                # 마지막 프로그램이면 다음 날 자정을 끝 시간으로 설정
                end_dt = start_dt.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)

            # 현재 시간이 프로그램 시작 시간과 다음 프로그램 시작 시간 사이에 있다면 현재 방송 중
            if start_dt <= now_utc9 < end_dt:
                current_program = program['program_title']
                break
        
        final_output['schedule'].append({
            "channel_name": channel,
            "current_program": current_program,
            "stream_url": cached_urls.get(channel, "URL_NOT_FOUND"), 
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

    # templates/index.html 파일을 렌더링합니다. (이 파일은 사용자에게 없으므로 생성해야 합니다.)
    # 여기서는 임시로 프론트엔드 코드를 제공할 수 없으므로, 상태만 보여주는 간단한 페이지를 렌더링한다고 가정합니다.
    return render_template('index.html', timestamp=timestamp_str)


@app.route('/schedule')
def get_schedule_api():
    """편성표 데이터와 스트림 URL을 JSON으로 반환하는 API 엔드포인트입니다."""
    
    # 1. 편성표 데이터 수집 (User-Agent가 추가되어 이제 성공해야 합니다)
    channel_names, timetable_data = get_naver_radio_schedule()
    
    if not channel_names:
        # 네이버 요청 실패 시 500 에러 반환 (기존 로직 유지)
        print("❌ get_schedule_api: 네이버로부터 편성표 데이터 수집 실패.")
        return jsonify({"error": "Failed to fetch schedule data from Naver."}), 500
        
    # 2. 💡 캐시 유효성 검사 및 동적 URL 추출/캐시 (Selenium 방어 로직)
    global STREAM_URL_CACHE
    
    if is_cache_valid():
        print(">> 캐시 유효함. Selenium 구동 생략.")
    else:
        print(">> 캐시 만료 또는 없음. Selenium 구동 시작.")
        try:
            fetch_all_dynamic_urls() # 순차적으로 구동되며, STREAM_URL_CACHE를 업데이트함
        except Exception as e:
            print(f"❌ 동적 URL 추출 중 오류 발생: {e}")
            # 오류 발생 시 기존 캐시(만료된 데이터)를 사용하거나, 고정 URL만 사용하여 서비스 중단 방지
            if not STREAM_URL_CACHE:
                STREAM_URL_CACHE = {name: CHANNEL_URLS[name] for name in CHANNEL_URLS if not (CHANNEL_URLS[name].endswith('_DYNAMIC') or CHANNEL_URLS[name].endswith('_SELENIUM'))}
            
    # 3. 데이터 처리 및 JSON 응답 반환
    final_json_data = process_schedule_data(channel_names, timetable_data)
    
    return jsonify(final_json_data)


# =========================================================================
# 4. 메인 실행
# =========================================================================

if __name__ == '__main__':
    # Render 환경에서 포트 자동 설정
    port = int(os.environ.get("PORT", 5000))
    # Render 환경에서는 0.0.0.0 바인딩이 필수
    app.run(host='0.0.0.0', port=port, debug=False)
