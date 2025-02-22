from config import NEXON_API_TOKEN, NEXON_API_BASE_URL
import aiohttp
from datetime import datetime, timedelta
import asyncio
import matplotlib.pyplot as plt
import io


class MapleAPIError(Exception):
    pass


async def get_character_ocid(character_name: str) -> str:
    """
    캐릭터 이름으로 OCID를 조회하는 함수
    """
    headers = {
        "x-nxopen-api-key": NEXON_API_TOKEN
    }

    async with aiohttp.ClientSession() as session:
        try:
            url = f"{NEXON_API_BASE_URL}/id?character_name={character_name}"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 404:
                    raise MapleAPIError("캐릭터를 찾을 수 없습니다")
                elif response.status != 200:
                    error_text = await response.text()
                    raise MapleAPIError(
                        f"API 오류 (상태 코드: {response.status}, 응답: {error_text})")

                data = await response.json()
                return data.get('ocid')

        except aiohttp.ClientError as e:
            raise MapleAPIError(f"네트워크 오류: {str(e)}")


async def get_character_exp_history(ocid: str):
    """
    캐릭터의 7일간 경험치 히스토리를 조회하는 함수
    """
    headers = {
        "x-nxopen-api-key": NEXON_API_TOKEN
    }

    exp_history = []
    today = datetime.now()

    # 오늘 데이터 먼저 조회 (date 파라미터 생략)
    async with aiohttp.ClientSession() as session:
        try:
            url = f"{NEXON_API_BASE_URL}/character/basic?ocid={ocid}"
            async with session.get(url, headers=headers, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    exp_history.append({
                        'date': f"{today.strftime('%Y-%m-%d')}T00:00+09:00",
                        'exp': data.get('character_exp', 0),
                        'level': data.get('character_level', 0),
                        'exp_rate': data.get('character_exp_rate', '0')
                    })
        except aiohttp.ClientError as e:
            raise MapleAPIError(f"네트워크 오류: {str(e)}")

    # 어제부터 6일 전까지의 데이터 조회
    for i in range(1, 7):
        date = (today - timedelta(days=i)).strftime("%Y-%m-%d")

        async with aiohttp.ClientSession() as session:
            try:
                url = f"{
                    NEXON_API_BASE_URL}/character/basic?ocid={ocid}&date={date}"
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        exp_history.append({
                            'date': f"{date}T00:00+09:00",
                            'exp': data.get('character_exp', 0),
                            'level': data.get('character_level', 0),
                            'exp_rate': data.get('character_exp_rate', '0')
                        })
                    elif response.status != 404:
                        error_text = await response.text()
                        raise MapleAPIError(
                            f"API 오류 (상태 코드: {response.status}, 응답: {error_text})")

            except aiohttp.ClientError as e:
                raise MapleAPIError(f"네트워크 오류: {str(e)}")

    # 날짜 순으로 정렬
    exp_history.sort(key=lambda x: x['date'])
    return exp_history


async def get_character_info(ocid: str):
    """
    OCID로 캐릭터 정보를 조회하는 함수
    """
    headers = {
        "x-nxopen-api-key": NEXON_API_TOKEN
    }

    async with aiohttp.ClientSession() as session:
        try:
            url = f"{NEXON_API_BASE_URL}/character/basic?ocid={ocid}"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 404:
                    raise MapleAPIError("캐릭터 정보를 찾을 수 없습니다")
                elif response.status != 200:
                    error_text = await response.text()
                    raise MapleAPIError(
                        f"API 오류 (상태 코드: {response.status}, 응답: {error_text})")

                return await response.json()

        except aiohttp.ClientError as e:
            raise MapleAPIError(f"네트워크 오류: {str(e)}")


async def get_character_exp_monthly(ocid: str, year: int, month: int):
    """
    캐릭터의 월간 경험치 히스토리를 조회하는 함수
    """
    headers = {
        "x-nxopen-api-key": NEXON_API_TOKEN
    }

    exp_history = []

    # 시작일과 종료일 계산
    start_date = datetime(year, month, 1)
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    end_date = next_month - timedelta(days=1)

    current_date = end_date
    while current_date >= start_date:
        # 미래 날짜는 건너뛰기
        if current_date > datetime.now():
            current_date -= timedelta(days=1)
            continue

        # 오늘 날짜는 date 파라미터 없이 요청
        if current_date.date() == datetime.now().date():
            url = f"{NEXON_API_BASE_URL}/character/basic?ocid={ocid}"
        else:
            date_str = current_date.strftime("%Y-%m-%d")
            url = f"{
                NEXON_API_BASE_URL}/character/basic?ocid={ocid}&date={date_str}"

        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url, headers=headers, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('character_exp') is not None:
                            exp_history.append({
                                'date': current_date.strftime("%Y-%m-%d"),
                                'exp': int(data.get('character_exp', 0)),
                                'level': int(data.get('character_level', 0)),
                                'exp_rate': float(data.get('character_exp_rate', '0'))
                            })
                    elif response.status != 404:
                        error_text = await response.text()
                        raise MapleAPIError(
                            f"API 오류 (상태 코드: {response.status}, 응답: {error_text})")

            except aiohttp.ClientError as e:
                raise MapleAPIError(f"네트워크 오류: {str(e)}")

        current_date -= timedelta(days=1)

    # 날짜 기준 내림차순 정렬
    return sorted(exp_history, key=lambda x: x['date'], reverse=True)


# 테스트 코드
async def main():
    try:
        character_name = "고양이메루"  # 테스트할 캐릭터 이름
        print(f"캐릭터 '{character_name}' 정보 조회 중...")

        # OCID 조회
        ocid = await get_character_ocid(character_name)
        print(f"OCID: {ocid}")

        if ocid:
            # 현재 월의 경험치 히스토리 조회
            now = datetime.now()
            history = await get_character_exp_monthly(ocid, now.year, now.month)
            print("\n월간 경험치 히스토리:")
            for data in history:
                print(f"날짜: {data['date']}, 레벨: {data['level']}, 경험치율: {
                      data['exp_rate']}%, 경험치: {data['exp']}")

    except MapleAPIError as e:
        print(f"오류 발생: {e}")
    except Exception as e:
        print(f"예상치 못한 오류: {e}")


if __name__ == "__main__":
    asyncio.run(main())
