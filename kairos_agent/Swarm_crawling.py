from selenium import webdriver
from bs4 import BeautifulSoup
import json
import time
import chromedriver_autoinstaller

def crawl_page_to_json(url):
    """
    주어진 URL의 내용을 크롤링하여 JSON 파일로 저장하는 함수.

    Args:
        url (str): 크롤링할 대상 URL.
        output_file (str): 크롤링 데이터를 저장할 JSON 파일 이름. 기본값은 'crawled_data.json'.

    Returns:
        str: 저장된 JSON 파일 경로.
    """
    # 크롬 드라이버 자동 설치 및 설정
    chromedriver_autoinstaller.install()
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    
    # 웹 드라이버 초기화
    driver = webdriver.Chrome(options=options)

    try:
        # 크롤링 대상 URL 열기
        driver.get(url)
        time.sleep(5)  # 페이지 로딩 대기

        # 페이지 소스 추출 및 BeautifulSoup 파싱
        html = driver.page_source
        soup = BeautifulSoup(html, "html.parser")

        # 페이지 전체 텍스트 추출
        page_content = soup.get_text(separator="\n").strip()

        # 데이터 저장
        data = {
            "url": url,
            "content": page_content
        }

        print(f"크롤링 완료: {url}")
        return data

    except Exception as e:
        print(f"Error occurred: {e}")
        return {"error": str(e)}

    finally:
        # 드라이버 종료
        driver.quit()
