import requests
from bs4 import BeautifulSoup
import threading
from collections import defaultdict
import datetime
import json
import time
import os # Render 환경 변수 사용을 위해 추가

# Flask 임포트
from flask import Flask, jsonify, render_template_string

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

# --- 1. CHANNEL_URLS (KBS3R, KBS한민족 최종 이름 반영) ---
# 이 딕셔너리는 URL 추출 타입을 정의하거나 고정 URL을 담고 있습니다.
CHANNEL_URLS = {
    # KBS Channels (모두 Selenium 기반 추출)
    'KBS클래식FM': 'KBS_SELENIUM',
    'KBS1R': 'KBS_SELENIUM',
    'KBS쿨FM': 'KBS_SELENIUM',
    'KBS해피FM': 'KBS_SELENIUM',
    'KBS3R': 'KBS_SELENIUM',
    'KBS한민족': 'KBS_SELENIUM',
    'KBSWorldRadio': 'KBS_SELENIUM',

    # MBC Channels (Dynamic 추출)
    'MBCFM4U': 'MBC_DYNAMIC',
    'MBC표준FM': 'MBC_DYNAMIC',

    # SBS Channels (Dynamic 추출)
    'SBS파워FM': 'SBS_DYNAMIC',
    'SBS러브FM': 'SBS_DYNAMIC',

    # 신규 동적 채널 3개 추가
    'BBS불교방송': 'BBS_DYNAMIC',
    'EBS교육방송': 'EBS_DYNAMIC',
    'CPBC 평화방송': 'CPBC_DYNAMIC',

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

# --- 1.5.1 Selenium 기반 동적 추출 (공통 함수 - Render 환경 맞춤) ---
def get_dynamic_stream_url_selenium(target_url, channel_name, selector_type, selector_value, pattern_to_find, wait_time_sec=5):
    chrome_options = Options()
    
    # 💡 Render/Heroku 환경을 위한 필수 옵션 설정
    chrome_options.add_argument("--headless=new") # 최신 headless 모드
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # 네트워크 로그 기록 활성화
    chrome_options.set_capability('goog:loggingPrefs', {'performance': 'ALL'})

    final_stream_url = None
    driver = None
    
    try:
        # 💡 WebDriver 경로 설정 (Render 환경에서는 PATH에 있으므로 생략)
        # 로컬 환경에서 실행 시: driver = webdriver.Chrome(options=chrome_options, executable_path='/path/to/chromedriver')
        driver = webdriver.Chrome(options=chrome_options) 
        
        # ... (이하 로직은 기존과 동일) ...
        driver.get(target_url)
        
        wait = WebDriverWait(driver, 10)
        
        # selector_value가 유효한 경우에만 버튼 클릭 및 대기 로직 수행
        if selector_value and selector_type:
            # 메인 재생 버튼 로드 및 클릭
            play_button = wait.until(
                EC.presence_of_element_located((selector_type, selector_value))
            )
            play_button.click()
        
        time.sleep(wait_time_sec) # 스트림 요청이 발생할 시간을 기다림
        
        # 네트워크 로그 분석
        logs = driver.get_log('performance')
        url_found = False
        
        for log in logs:
            try:
                message = json.loads(log['message'])
                params = message.get('message', {}).get('params', {})
                request = params.get('request', {})
                
                url = request.get('url', '')
                if url and pattern_to_find in url:
                    final_stream_url = url
                    url_found = True
                    break
            except Exception:
                continue
        
        if not url_found:
             print(f"❌ Network Log에서 '{pattern_to_find}' 패턴을 찾지 못했습니다.")
            
    except SelTimeoutException:
        print(f"❌ {channel_name}: 버튼 로드/페이지 로드 시간 초과.")
    except Exception as e:
        print(f"❌ Selenium 실행 중 예외 발생: {e}")
        
    finally:
        if driver:
            driver.quit()
            
    return final_stream_url

# --- 1.5.2 MBC Stream URL 추출 함수 (로직 변경 없음) ---
def get_mbc_stream_url(channel_name):
    if channel_name == 'MBCFM4U':
        target_url = 'https://miniwebapp.imbc.com/index?channel=mfm'
        pattern = 'playlist.m3u8?_lsu_sa_='
    elif channel_name == 'MBC표준FM':
        target_url = 'https://miniwebapp.imbc.com/index?channel=sfm'
        pattern = 'playlist.m3u8?_lsu_sa_='
    else:
        return None
    return get_dynamic_stream_url_selenium(target_url, channel_name, By.ID, 'play_pause_btn', pattern)

# --- 1.5.3 SBS Stream URL 추출 함수 (버튼 클릭 로직 제거 반영) ---
def get_sbs_stream_url(channel_name):
    if channel_name == 'SBS파워FM':
        target_url = 'https://www.sbs.co.kr/live/S17?div=live_end'
        pattern = 'radiolive.sbs.co.kr/powerpc/powerfm.stream/playlist.m3u8?token='
    elif channel_name == 'SBS러브FM':
        target_url = 'https://www.sbs.co.kr/live/S08?div=live_end'
        pattern = 'radiolive.sbs.co.kr/lovepc/lovefm.stream/playlist.m3u8?token='
    else:
        return None
    
    # 버튼 클릭 로직을 건너뛰기 위해 None 전달
    return get_dynamic_stream_url_selenium(target_url, channel_name, None, None, pattern)

# --- 1.5.4 KBS Selenium Stream URL 추출 함수 (로직 변경 없음) ---
def get_kbs_selenium_url(channel_name):
    kbs_selenium_map = {
        'KBS해피FM': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=22&ch_type=radioList&bora=off&chat=off', 'pattern': '2radio-ad.gscdn.kbs.co.kr/2radio_ad_192_1.m3u8?Policy='},
        'KBS쿨FM': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=25&ch_type=radioList&bora=off&chat=off', 'pattern': '2fm-ad.gscdn.kbs.co.kr/2fm_ad_192_1.m3u8?Policy='},
        'KBS클래식FM': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=24&ch_type=radioList&bora=off&chat=off', 'pattern': '1fm.gscdn.kbs.co.kr/1fm_192_2.m3u8?Policy='},
        'KBS1R': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=21&ch_type=radioList&bora=off&chat=off', 'pattern': '1radio.gscdn.kbs.co.kr/1radio_192_4.m3u8?Policy='},
        'KBS3R': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=23&ch_type=radioList&bora=off&chat=off', 'pattern': '3radio.gscdn.kbs.co.kr/3radio_192_3.m3u8?Policy='},
        'KBS한민족': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=26&ch_type=radioList&bora=off&chat=off', 'pattern': 'hanminjokradio.gscdn.kbs.co.kr/hanminjokradio_192_2.m3u8?Policy='},
        'KBSWorldRadio': {'url': 'https://onair.kbs.co.kr/index.html?sname=onair&stype=live&ch_code=I92&ch_type=radioList&bora=off&chat=off', 'pattern': 'worldradio.gscdn.kbs.co.kr/worldradio_192_4.m3u8?Policy='}
    }
    info = kbs_selenium_map.get(channel_name)
    if not info: return None
    
    # KBS는 클릭 필요
    return get_dynamic_stream_url_selenium(info['url'], channel_name, By.CSS_SELECTOR, 'div[aria-label="재생"]', info['pattern'])

# --- 1.5.5 기타 방송사 Dynamic Stream URL 추출 함수 (BBS, EBS, CPBC) ---
def get_other_dynamic_url(channel_name):
    info_map = {
        'BBS불교방송': {'url': 'https://www.bbs.or.kr/HOME2/?ACT=ONAIR&pType=RADIO', 'pattern': 'bbslive.clouducs.com/bbsradio-live/livestream/chunklist_', 'selector_type': None, 'selector_value': None, 'wait_time': 5},
        'EBS교육방송': {'url': 'https://www.ebs.co.kr/onair?channelCodeString=radio', 'pattern': 'liveotu.ebs.co.kr/fm/fm.smil/playlist.m3u8?Policy=', 'selector_type': By.CSS_SELECTOR, 'selector_value': 'button.mpv-toggle-btn.mpv-button.mpv-bctrl-btn.mpv-pause', 'wait_time': 20},
        'CPBC 평화방송': {'url': 'https://www.cpbc.co.kr/onair.html?channel=radio', 'pattern': 'cdn-radio-seoul.cpbc.co.kr/cpbcseoul/playlist.m3u8?token=', 'selector_type': None, 'selector_value': None, 'wait_time': 5}
    }
    info = info_map.get(channel_name)
    if not info: return None
    
    return get_dynamic_stream_url_selenium(
        info['url'], channel_name, info['selector_type'], info['selector_value'], info['pattern'], wait_time_sec=info['wait_time']
    )

# --- 1.6 모든 동적 URL을 가져오는 함수 (캐시 적용) ---
def fetch_all_dynamic_urls():
    global STREAM_URL_CACHE, CACHE_LAST_UPDATED
    
    now = datetime.datetime.now()
    
    # 캐시 만료 확인
    if CACHE_LAST_UPDATED and (now - CACHE_LAST_UPDATED).total_seconds() < CACHE_EXPIRATION_SECONDS:
        print(">> 캐시된 동적 URL 사용.")
        return STREAM_URL_CACHE
        
    print(">> 동적 URL 캐시 만료. 새롭게 추출 시작.")
    new_cache = {}
    
    channels_to_fetch = [name for name, link in CHANNEL_URLS.items() if link.endswith('_DYNAMIC') or link.endswith('_SELENIUM')]
    
    threads = []
    results = {}
    
    def fetch_url(channel_name, link_type):
        url = None
        if link_type == 'MBC_DYNAMIC': url = get_mbc_stream_url(channel_name)
        elif link_type == 'SBS_DYNAMIC': url = get_sbs_stream_url(channel_name)
        elif link_type == 'KBS_SELENIUM': url = get_kbs_selenium_url(channel_name)
        elif link_type in ('BBS_DYNAMIC', 'EBS_DYNAMIC', 'CPBC_DYNAMIC'): url = get_other_dynamic_url(channel_name)
        
        results[channel_name] = url if url else "URL_NOT_FOUND"

    # 스레딩을 사용하여 병렬 추출 (속도 향상)
    for channel_name in channels_to_fetch:
        link_type = CHANNEL_URLS[channel_name]
        t = threading.Thread(target=fetch_url, args=(channel_name, link_type))
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join() # 모든 스레드가 완료될 때까지 대기
        
    new_cache = results
    
    # 고정 URL 캐시에 추가
    for name, link in CHANNEL_URLS.items():
        if not (link.endswith('_DYNAMIC') or link.endswith('_SELENIUM')):
            new_cache[name] = link
            
    STREAM_URL_CACHE = new_cache
    CACHE_LAST_UPDATED = now
    
    print(f">> 동적 URL 추출 완료. 총 {len(new_cache)}개 채널 URL 업데이트됨.")
    return STREAM_URL_CACHE


# =========================================================================
# 2. 네이버 편성표 데이터 수집 함수 (로직 변경 없음)
# =========================================================================

def get_naver_radio_schedule():
    # ... (기존 Tkinter 코드의 get_naver_radio_schedule 함수와 동일)
    naver_url = 'https://search.naver.com/search.naver?query=%EB%9D%BC%EB%94%94%EC%98%A4+%ED%8E%B8%EC%84%B1%ED%91%9C'
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(naver_url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        channel_elements = soup.select('.list_left .channel_list .item a')
        channel_names = [elem.text.strip() for elem in channel_elements]
        timeline_rows = soup.select('.timeline_body .list_right .item')
        
        timetable_data = defaultdict(list)
        
        # 1단계: 채널 이름 변경 (Naver 채널 목록 기준으로 CHANNEL_URLS 키로 매핑)
        renamed_channel_names = []
        # 현재 누락이 적다고 하셨으므로, 기존의 3개 매핑만 유지
        name_mapping = {
            'KBS2R': 'KBS해피FM',
            'KBS2FM': 'KBS쿨FM',
            'KBS1FM': 'KBS클래식FM',
        }
        
        for name in channel_names:
            mapped_name = name_mapping.get(name, name)
            if mapped_name in CHANNEL_URLS:
                renamed_channel_names.append(mapped_name)

        # 2단계: 편성표 데이터 수집
        valid_indices = [idx for idx, name in enumerate(channel_names) if name_mapping.get(name, name) in CHANNEL_URLS]
        
        for idx_list, idx_naver in enumerate(valid_indices):
            channel_name = renamed_channel_names[idx_list]
            
            if idx_naver < len(timeline_rows):
                row = timeline_rows[idx_naver]
                program_blocks = row.find_all('div', class_='ind_program')
                
                for block in program_blocks:
                    title_tag = block.select_one('.pr_title._text')
                    time_tag = block.select_one('.sub_info .time')
                    
                    title = title_tag.text.strip() if title_tag else "정보 없음"
                    time_str = time_tag.text.strip() if time_tag else "00:00"
                    is_on_air = 'on' in block.get('class', [])
                    
                    if title != "방송없음":
                        timetable_data[channel_name].append({
                            'time': time_str,
                            'title': title,
                            'on_air': is_on_air
                        })
            # else 경고 메시지는 서버 환경에서는 불필요하므로 생략

        final_channel_list = renamed_channel_names
        return final_channel_list, timetable_data
    except Exception as e:
        print(f"편성표 수집 오류: {e}")
        return [], {}

# =========================================================================
# 3. 데이터 처리 및 Flask API 엔드포인트
# =========================================================================

# Tkinter의 process_schedule_data 로직을 그대로 사용 (시간 계산)
def parse_time_to_minutes(time_str):
    h, m = map(int, time_str.split(':'))
    return h * 60 + m

def get_all_30min_slots():
    slots = []
    for h in range(24):
        slots.append(datetime.time(h, 0))
        slots.append(datetime.time(h, 30))
    return slots

def process_schedule_data(channel_names, timetable_data):
    # ... (기존의 process_schedule_data 함수 로직과 동일)
    now = datetime.datetime.now()
    all_slots = get_all_30min_slots()
    full_day_schedule = defaultdict(lambda: {slot: {'title': '', 'on_air': False, 'duration_slots': 1, 'is_merged': False} for slot in all_slots})

    # 1. 30분 슬롯 단위로 프로그램 매핑
    for channel in channel_names:
        programs = timetable_data[channel]
        if not programs: continue
        programs_with_end = programs + [{'time': '00:00', 'title': 'END', 'on_air': False}]
        processed_programs = []
        for i in range(len(programs)):
            p1 = programs_with_end[i]
            p2 = programs_with_end[i+1]
            p1_minutes = parse_time_to_minutes(p1['time'])
            p2_minutes = parse_time_to_minutes(p2['time'])
            if p2['time'] == '00:00' and p1_minutes != 0: p2_minutes = 24 * 60
            elif p2_minutes < p1_minutes: p2_minutes += 24 * 60
            duration_minutes = p2_minutes - p1_minutes
            duration_slots = max(1, duration_minutes // 30)
            processed_programs.append({'start_time': p1['time'], 'title': p1['title'], 'on_air': p1['on_air'], 'duration_slots': duration_slots})
        
        for program in processed_programs:
            try:
                start_h, start_m = map(int, program['start_time'].split(':'))
                start_time_obj = datetime.time(start_h, start_m)
                start_index = all_slots.index(start_time_obj)
                for i in range(program['duration_slots']):
                    slot_index = (start_index + i) % 48
                    current_slot_time = all_slots[slot_index]
                    if i == 0:
                        full_day_schedule[channel][current_slot_time] = {
                            'title': program['title'], 'on_air': program['on_air'], 'duration_slots': program['duration_slots'], 'is_merged': False
                        }
                    else:
                        full_day_schedule[channel][current_slot_time] = {
                            'title': program['title'], 'on_air': program['on_air'], 'duration_slots': 1, 'is_merged': True
                        }
            except Exception:
                continue
    
    # 2. 현재 시간 기준 2.5시간 범위 슬롯 계산
    start_dt_raw = now - datetime.timedelta(hours=1)
    end_dt_raw = now + datetime.timedelta(hours=1, minutes=30)
    total_minutes_start = start_dt_raw.hour * 60 + start_dt_raw.minute
    total_minutes_aligned_start = (total_minutes_start // 30) * 30
    total_minutes_end = end_dt_raw.hour * 60 + end_dt_raw.minute
    total_minutes_aligned_end = ((total_minutes_end + 29) // 30) * 30
    today_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
    dt_start_aligned = today_date + datetime.timedelta(minutes=total_minutes_aligned_start)
    dt_end_aligned = today_date + datetime.timedelta(minutes=total_minutes_aligned_end)
    if dt_start_aligned > now + datetime.timedelta(minutes=10): dt_start_aligned -= datetime.timedelta(days=1)
    if dt_end_aligned < now - datetime.timedelta(minutes=10): dt_end_aligned += datetime.timedelta(days=1)
    
    target_slots_dt = []
    current_dt = dt_start_aligned
    while current_dt < dt_end_aligned:
        target_slots_dt.append(current_dt)
        current_dt += datetime.timedelta(minutes=30)

    # 3. 최종 JSON 구조 생성
    ordered_channels = [name for name in channel_names if name in CHANNEL_URLS]
    
    final_output = {
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "time_headers": [dt.strftime("%H:%M") for dt in target_slots_dt],
        "schedule": []
    }
    
    # 동적/고정 URL 캐시 데이터를 가져옵니다.
    cached_urls = fetch_all_dynamic_urls()
    
    for channel in ordered_channels:
        channel_schedule = []
        for time_slot_dt in target_slots_dt:
            time_slot_key = time_slot_dt.time()
            program_info = full_day_schedule[channel][time_slot_key]
            
            # JSON 출력을 위해 datetime.time 객체를 문자열로 변환
            program_info_json = {
                'time_slot': time_slot_dt.strftime("%H:%M"),
                'title': program_info['title'],
                'on_air': program_info['on_air'],
                'duration_slots': program_info['duration_slots'],
                'is_merged': program_info['is_merged']
            }
            channel_schedule.append(program_info_json)
            
        final_output['schedule'].append({
            "channel_name": channel,
            "stream_url": cached_urls.get(channel, "URL_PROCESSING_ERROR"), # 캐시된 URL 포함
            "programs": channel_schedule
        })
        
    return final_output

@app.route('/')
def home():
    """간단한 HTML 페이지를 반환하여 서버가 작동하는지 확인합니다."""
    # Render에 배포할 때, 서버가 작동하는지 UptimeRobot이 확인할 수 있도록 HTML 응답을 제공합니다.
    return render_template_string("<h1>라디오 편성표 서버가 작동 중입니다.</h1><p>API 엔드포인트: <a href='/schedule'>/schedule</a></p><p>최근 업데이트: {{ timestamp }}</p>", 
                                  timestamp=CACHE_LAST_UPDATED.strftime('%Y-%m-%d %H:%M:%S') if CACHE_LAST_UPDATED else "N/A")

@app.route('/schedule')
def get_schedule_api():
    """편성표 데이터와 스트림 URL을 JSON으로 반환하는 API 엔드포인트입니다."""
    
    # 1. 편성표 데이터 수집
    channel_names, timetable_data = get_naver_radio_schedule()
    
    if not channel_names:
        return jsonify({"error": "Failed to fetch schedule data from Naver."}), 500
        
    # 2. 데이터 처리 및 동적 URL 추출/캐시
    final_json_data = process_schedule_data(channel_names, timetable_data)
    
    # 3. JSON 응답 반환
    return jsonify(final_json_data)

# =========================================================================
# 4. 메인 실행
# =========================================================================
if __name__ == '__main__':
    # Render 환경에서 포트 자동 설정
    port = int(os.environ.get("PORT", 5000))
    # Render 환경에서는 0.0.0.0 바인딩이 필수
    app.run(host='0.0.0.0', port=port, debug=False)
