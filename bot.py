import discord
from discord.ext import commands
import matplotlib.pyplot as plt
from datetime import datetime, time, timedelta
import io
from config import DISCORD_BOT_TOKEN
from main import get_character_ocid, get_character_info, get_character_exp_history, get_character_exp_monthly, MapleAPIError
import matplotlib.font_manager as fm
from discord.ext import tasks
import aiohttp
from bs4 import BeautifulSoup
import pytz  # 시간대 처리를 위한 모듈 추가

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"{bot.user}로 로그인 되었습니다.")
    await bot.change_presence(activity=discord.Game("메이플스토리"))


def create_exp_graph(exp_history: list, character_name: str):
    """
    경험치 히스토리로 그래프를 생성하는 함수
    """
    import platform
    system = platform.system()

    if system == 'Darwin':  # macOS
        font_path = fm.findfont(fm.FontProperties(family='AppleGothic'))
    elif system == 'Windows':  # Windows
        font_path = fm.findfont(fm.FontProperties(family='Malgun Gothic'))
    else:  # Linux 등
        try:
            font_path = fm.findfont(fm.FontProperties(family='NanumGothic'))
        except:
            font_path = fm.findfont(fm.FontProperties(family='sans-serif'))

    plt.rcParams['font.family'] = ['xkcd', 'sans-serif']
    plt.rcParams['font.size'] = 12
    plt.rcParams['axes.unicode_minus'] = False

    dates = []
    exp_rates = []
    levels = []

    for history in exp_history:
        date = datetime.strptime(history['date'].split('T')[0], '%Y-%m-%d')
        dates.append(date.strftime('%m/%d'))
        exp_rates.append(float(history.get('exp_rate', '0')))
        levels.append(int(history['level']))

    # 레벨 범위 계산 (100 단위)
    max_level = max(levels)
    level_range_start = (max_level // 100) * 100  # 100 단위로 내림
    level_range_end = ((max_level // 100) + 1) * 100  # 100 단위로 올림

    with plt.xkcd():
        fig, (ax1, ax2) = plt.subplots(
            2, 1, figsize=(12, 8), height_ratios=[2, 1])
        fig.patch.set_facecolor('white')

        # 경험치% 바 그래프
        bars1 = ax1.bar(dates, exp_rates, color='lightgreen',
                        edgecolor='black', linewidth=2)
        ax1.set_title(f"{character_name}의 경험치/레벨 변화",
                      fontsize=16, pad=20, fontproperties=fm.FontProperties(fname=font_path))
        ax1.set_ylabel('경험치%',
                       fontsize=12, fontproperties=fm.FontProperties(fname=font_path))

        # 바 위에 값 표시
        for bar in bars1:
            height = bar.get_height()
            ax1.text(bar.get_x() + bar.get_width()/2., height,
                     f'{height:.2f}%',
                     ha='center', va='bottom',
                     fontproperties=fm.FontProperties(fname=font_path))

        # 레벨 바 그래프
        bars2 = ax2.bar(dates, levels, color='salmon',
                        edgecolor='black', linewidth=2)
        ax2.set_xlabel('날짜',
                       fontsize=12, fontproperties=fm.FontProperties(fname=font_path))
        ax2.set_ylabel('레벨',
                       fontsize=12, fontproperties=fm.FontProperties(fname=font_path))

        # 레벨 범위 설정
        ax2.set_ylim(level_range_start, level_range_end)

        # 바 위에 값 표시
        for bar in bars2:
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                     f'{int(height)}',
                     ha='center', va='bottom',
                     fontproperties=fm.FontProperties(fname=font_path))

        # x축 레이블 회전
        plt.setp(ax1.get_xticklabels())
        plt.setp(ax2.get_xticklabels())

        # 여백 조정
        plt.tight_layout()

        # 그래프를 바이트 스트림으로 저장
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close()

        return buf


@bot.command()
async def 주간(ctx, character_name: str):
    """
    캐릭터의 정보와 경험치 그래프를 조회합니다
    """
    try:
        loading_msg = await ctx.send("캐릭터 정보를 조회중입니다...")

        # OCID 조회
        ocid = await get_character_ocid(character_name)
        if not ocid:
            await loading_msg.edit(content="캐릭터를 찾을 수 없습니다.")
            return

        # 캐릭터 정보와 경험치 히스토리 동시 조회
        info = await get_character_info(ocid)
        exp_history = await get_character_exp_history(ocid)

        # 캐릭터 이미지 URL 설정
        character_image = info.get('character_image', '')
        if character_image:
            character_image += "?action=A00&emotion=E00"

        # 기본 정보 임베드 생성
        embed = discord.Embed(
            title=f"{character_name}의 정보",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )

        # 기본 정보
        embed.add_field(name="레벨", value=f"{info.get(
            'character_level', 'N/A')} ({info.get('character_exp_rate', '0')}%)", inline=True)
        embed.add_field(name="직업", value=f"{info.get(
            'character_class', 'N/A')} ({info.get('character_class_level', '')}차)", inline=True)
        embed.add_field(name="월드", value=info.get(
            'world_name', 'N/A'), inline=True)

        # 추가 정보
        embed.add_field(name="길드", value=info.get(
            'character_guild_name', '없음'), inline=True)
        embed.add_field(name="성별", value=info.get(
            'character_gender', 'N/A'), inline=True)
        embed.add_field(name="경험치", value=format(
            info.get('character_exp', 0), ','), inline=True)

        # 상태 정보
        embed.add_field(name="최근 접속", value="⭕" if info.get(
            'access_flag') == "true" else "❌", inline=True)
        embed.add_field(name="해방 퀘스트", value="완료" if info.get(
            'liberation_quest_clear_flag') == "true" else "미완료", inline=True)

        # 캐릭터 이미지 설정
        if character_image:
            embed.set_thumbnail(url=character_image)

        # 푸터에 생성일 추가
        create_date = info.get('character_date_create', '').split('T')[0]
        if create_date:
            embed.set_footer(text=f"캐릭터 생성일: {create_date}")

        # 경험치 그래프 생성
        if exp_history:
            graph_buf = create_exp_graph(exp_history, character_name)
            file = discord.File(graph_buf, filename="exp_graph.png")
            embed.set_image(url="attachment://exp_graph.png")
            await loading_msg.delete()
            await ctx.send(file=file, embed=embed)
        else:
            await loading_msg.edit(content=None, embed=embed)

    except MapleAPIError as e:
        await ctx.send(f"❌ 오류: {str(e)}")
    except Exception as e:
        await ctx.send("⚠️ 내부 오류가 발생했습니다")
        print(f"Unexpected error: {str(e)}")


@bot.command()
async def info(ctx, character_name: str):
    """
    캐릭터의 기본 정보를 조회합니다
    """
    try:
        loading_msg = await ctx.send("캐릭터 정보를 조회중입니다...")

        # OCID 조회
        ocid = await get_character_ocid(character_name)
        if not ocid:
            await loading_msg.edit(content="캐릭터를 찾을 수 없습니다.")
            return

        # 캐릭터 정보 조회
        info = await get_character_info(ocid)

        # 캐릭터 이미지 URL 설정
        character_image = info.get('character_image', '')
        if character_image:
            character_image += "?action=A00&emotion=E00"

        # 기본 정보 임베드 생성
        embed = discord.Embed(
            title=f"{character_name}의 정보",
            color=0x00ff00,
            timestamp=discord.utils.utcnow()
        )

        # 기본 정보
        embed.add_field(name="레벨", value=f"{info.get(
            'character_level', 'N/A')} ({info.get('character_exp_rate', '0')}%)", inline=True)
        embed.add_field(name="직업", value=f"{info.get(
            'character_class', 'N/A')} ({info.get('character_class_level', '')}차)", inline=True)
        embed.add_field(name="월드", value=info.get(
            'world_name', 'N/A'), inline=True)

        # 추가 정보
        embed.add_field(name="길드", value=info.get(
            'character_guild_name', '없음'), inline=True)
        embed.add_field(name="성별", value=info.get(
            'character_gender', 'N/A'), inline=True)
        embed.add_field(name="경험치", value=format(
            info.get('character_exp', 0), ','), inline=True)

        # 상태 정보
        embed.add_field(name="최근 접속", value="⭕" if info.get(
            'access_flag') == "true" else "❌", inline=True)
        embed.add_field(name="해방 퀘스트", value="완료" if info.get(
            'liberation_quest_clear_flag') == "true" else "미완료", inline=True)

        # 캐릭터 이미지 설정
        if character_image:
            embed.set_thumbnail(url=character_image)

        # 푸터에 생성일 추가
        create_date = info.get('character_date_create', '').split('T')[0]
        if create_date:
            embed.set_footer(text=f"캐릭터 생성일: {create_date}")

        # 로딩 메시지를 결과로 교체
        await loading_msg.edit(content=None, embed=embed)

    except MapleAPIError as e:
        await ctx.send(f"❌ 오류: {str(e)}")
    except Exception as e:
        await ctx.send("⚠️ 내부 오류가 발생했습니다")
        print(f"Unexpected error: {str(e)}")


@bot.command()
async def 월간(ctx, character_name: str, *args):
    """
    캐릭터의 월간 경험치 획득량을 히트맵으로 보여줍니다
    """
    try:
        now = datetime.now()

        # 날짜 파라미터 처리
        if args:
            try:
                year = int(args[0])
                month = int(args[1])
                if not (1 <= month <= 12):
                    raise ValueError
            except (ValueError, IndexError):
                await ctx.send("❌ 올바른 연도와 월을 입력해주세요. (예: !monthly 캐릭터명 2024 3)")
                return
        else:
            year = now.year
            month = now.month

        loading_msg = await ctx.send(f"{year}년 {month}월 경험치 데이터를 조회중입니다...")

        # OCID 조회
        ocid = await get_character_ocid(character_name)
        if not ocid:
            await loading_msg.edit(content="캐릭터를 찾을 수 없습니다.")
            return

        # 월간 경험치 히스토리 조회
        exp_history = await get_character_exp_monthly(ocid, year, month)
        if not exp_history:
            await loading_msg.edit(content="해당 월의 데이터가 없습니다.")
            return

        # 일일 경험치 획득량 계산
        daily_gains = []
        for i in range(len(exp_history)-1):
            today = exp_history[i]
            yesterday = exp_history[i+1]

            today_exp_rate = float(today.get('exp_rate', '0'))
            yesterday_exp_rate = float(yesterday.get('exp_rate', '0'))
            today_level = int(today['level'])
            yesterday_level = int(yesterday['level'])

            # 경험치 증가량 계산
            if today_level == yesterday_level:
                # 레벨이 같을 때: 오늘% - 어제%
                exp_gain_rate = today_exp_rate - yesterday_exp_rate
                exp_text = f"+{exp_gain_rate:.3f}%"
            else:
                # 레벨업했을 때: (100 * 레벨업 수 + 오늘%) - 어제%
                level_diff = today_level - yesterday_level
                exp_gain_rate = (100 * level_diff +
                                 today_exp_rate) - yesterday_exp_rate
                exp_text = f"{level_diff}↑\n+{exp_gain_rate:.2f}%"

            daily_gains.append({
                'date': today['date'],
                'exp_gain_rate': max(0, exp_gain_rate),  # 음수 경험치는 0으로 처리
                'level': today_level,
                'is_levelup': today_level > yesterday_level,
                'exp_text': exp_text,
                'level_diff': level_diff if today_level > yesterday_level else 0
            })

        # 히트맵 생성
        buf = create_monthly_heatmap(daily_gains, character_name, year, month)

        # 결과 전송
        file = discord.File(buf, filename="exp_heatmap.png")
        embed = discord.Embed(
            title=f"{character_name}의 {year}년 {month}월 경험치 획득",
            color=0x00ff00
        )
        embed.set_image(url="attachment://exp_heatmap.png")
        await loading_msg.delete()
        await ctx.send(file=file, embed=embed)

    except MapleAPIError as e:
        await ctx.send(f"❌ 오류: {str(e)}")
    except Exception as e:
        await ctx.send("⚠️ 내부 오류가 발생했습니다")
        print(f"Unexpected error: {str(e)}")


def create_monthly_heatmap(daily_gains, character_name, year, month):
    """
    월간 경험치 획득량을 달력 형태의 히트맵으로 생성하는 함수
    """
    import calendar
    import numpy as np

    # 폰트 설정
    import platform
    system = platform.system()
    if system == 'Darwin':
        font_path = fm.findfont(fm.FontProperties(family='AppleGothic'))
    elif system == 'Windows':
        font_path = fm.findfont(fm.FontProperties(family='Malgun Gothic'))
    else:
        try:
            font_path = fm.findfont(fm.FontProperties(family='NanumGothic'))
        except:
            font_path = fm.findfont(fm.FontProperties(family='sans-serif'))

    plt.rcParams['font.family'] = ['xkcd', 'sans-serif']
    plt.rcParams['font.size'] = 12
    plt.rcParams['axes.unicode_minus'] = False

    # 달력 데이터 준비
    cal = calendar.monthcalendar(year, month)

    # 경험치 데이터를 딕셔너리로 변환
    exp_dict = {gain['date']: gain['exp_gain_rate'] for gain in daily_gains}

    # 경험치 획득량에 따른 색상 강도 계산
    if daily_gains:
        max_exp = max(gain['exp_gain_rate'] for gain in daily_gains)
        quartiles = [
            0,  # 0% (no exp)
            max_exp * 0.25,  # 25%
            max_exp * 0.5,  # 50%
            max_exp * 0.75,  # 75%
        ]
    else:
        quartiles = [0, 0, 0, 0]

    # 색상 맵 정의 (5단계)
    colors = ['#ebedf0',  # 0 (no contribution)
              '#9be9a8',  # 1-25%
              '#40c463',  # 26-50%
              '#30a14e',  # 51-75%
              '#216e39']  # 76-100%

    with plt.xkcd():
        fig, ax = plt.subplots(figsize=(15, 10))
        fig.patch.set_facecolor('white')

        # 요일 레이블
        days = ['월', '화', '수', '목', '금', '토', '일']
        for i, day in enumerate(days):
            ax.text(i + 0.5, 6.5, day, ha='center', va='center',
                    fontproperties=fm.FontProperties(fname=font_path))

        # 달력 그리기 (reversed 제거)
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day != 0:
                    date_str = f"{year}-{month:02d}-{day:02d}"
                    exp_gain_rate = exp_dict.get(date_str, 0)

                    # 경험치 획득량에 따른 색상 결정
                    if exp_gain_rate == 0:
                        color_idx = 0
                    elif exp_gain_rate <= quartiles[1]:
                        color_idx = 1
                    elif exp_gain_rate <= quartiles[2]:
                        color_idx = 2
                    elif exp_gain_rate <= quartiles[3]:
                        color_idx = 3
                    else:
                        color_idx = 4

                    color = colors[color_idx]

                    # 날짜 칸 그리기
                    ax.add_patch(plt.Rectangle((day_num, 5-week_num),  # y좌표 수정
                                               1, 1, facecolor=color,
                                               edgecolor='black'))

                    # 날짜 표시
                    ax.text(day_num + 0.05, 5-week_num + 0.8, str(day),  # y좌표 수정
                            fontsize=8, ha='left', va='top',
                            fontproperties=fm.FontProperties(fname=font_path))

                    # 경험치 증가율 표시
                    if exp_gain_rate > 0:
                        for gain in daily_gains:
                            if gain['date'] == date_str:
                                ax.text(day_num + 0.5, 5-week_num + 0.4, gain['exp_text'],
                                        fontsize=8, ha='center', va='center',
                                        fontproperties=fm.FontProperties(fname=font_path))
                                break

        # 그래프 설정
        ax.set_title(f"{character_name}의 {year}년 {month}월 경험치 획득량",
                     fontproperties=fm.FontProperties(fname=font_path), pad=20)
        ax.set_xlim(-0.2, 7.2)
        ax.set_ylim(-0.2, 7.2)
        ax.axis('off')

        # 범례 추가
        legend_elements = [plt.Rectangle((0, 0), 1, 1, facecolor=color, edgecolor='black')
                           for color in colors]
        legend_labels = ['경험치 없음', '하위 25%', '하위 50%', '하위 75%', '상위 25%']
        ax.legend(legend_elements, legend_labels,
                  title='경험치 획득량',
                  loc='center left',
                  bbox_to_anchor=(1.05, 0.5),
                  title_fontproperties=fm.FontProperties(fname=font_path),
                  prop=fm.FontProperties(fname=font_path))

        plt.tight_layout()

        # 그래프를 바이트 스트림으로 저장
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close()

        return buf


@bot.command()
async def 환산(ctx, name=None):
    if name is None:
        await ctx.send("닉네임을 입력해주세요. 예시: !환산 닉네임")
        return
    if name == "사이트맵":
        await ctx.send("\nhttps://maplescouter.com/sitemap")
        return
    url = f"https://maplescouter.com/info?name={name}"
    await ctx.send(f"{name}의 환산 확인:\n{url}")


@bot.command()
async def 썬데이메이플(ctx):
    try:
        base_url = "https://maplestory.nexon.com/News/Event/Ongoing"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, headers=headers) as response:
                if response.status == 200:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')

                    event_list = soup.select_one('.contents_wrap .event_board')
                    if event_list:
                        events = event_list.select('li')
                        found = False
                        for event in events:
                            title = event.select_one('dd, .title, p, span')
                            if title:
                                title_text = title.text.strip().lower()
                                search_terms = [
                                    '썬데이', '스페셜 썬데이', 'sunday', '스페셜썬데이']
                                if any(term in title_text for term in search_terms):
                                    found = True
                                    link = event.select_one('a')['href']
                                    post_url = f"https://maplestory.nexon.com{
                                        link}"

                                    async with session.get(post_url, headers=headers) as post_response:
                                        if post_response.status == 200:
                                            post_html = await post_response.text()
                                            post_soup = BeautifulSoup(
                                                post_html, 'html.parser')

                                            img = post_soup.find('img', alt=lambda x: x and any(
                                                term in x.lower() for term in search_terms))
                                            if not img:
                                                img = post_soup.select_one(
                                                    '.event_thumbnail img, .content img')

                                            if img and img.get('src'):
                                                await ctx.send(img['src'])
                                            else:
                                                await ctx.send("이미지를 찾을 수 없습니다.")
                                            return

                        if not found:
                            await ctx.send("현재 진행중인 썬데이메이플 이벤트를 찾을 수 없습니다.")
                    else:
                        await ctx.send("이벤트 목록을 찾을 수 없습니다.")
                else:
                    await ctx.send("이벤트 목록을 불러오는데 실패했습니다.")
    except Exception as e:
        await ctx.send(f"명령어 실행 중 오류가 발생했습니다: {str(e)}")


@bot.event
async def on_ready():
    print(f"{bot.user}로 로그인 되었습니다.")
    await bot.change_presence(activity=discord.Game("메이플스토리"))
    썬데이메이플_자동알림.start()  # 자동 알림 시작
    print("썬데이메이플 자동 알림이 시작되었습니다.")


@tasks.loop(time=time(hour=1, minute=1))
async def 썬데이메이플_자동알림():
    try:
        # 한국 시간 가져오기
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.now(kst)
        print(f"현재 시간: {now}, 요일: {now.weekday()}")  # 디버깅용

        if now.weekday() == 4:  # 금요일 체크
            print("금요일 확인됨, 알림 시작")  # 디버깅용
            for guild in bot.guilds:
                try:
                    # 봇의 권한 확인
                    bot_member = guild.me
                    print(f"\n서버 '{guild.name}'에서의 봇 권한:")
                    print(
                        f"채널 보기: {bot_member.guild_permissions.view_channel}")
                    print(f"메시지 보내기: {
                          bot_member.guild_permissions.send_messages}")
                    print(
                        f"파일 첨부: {bot_member.guild_permissions.attach_files}")
                    print(
                        f"임베드 링크: {bot_member.guild_permissions.embed_links}")

                    category = discord.utils.find(
                        lambda c: c.name.lower() == "메이플",
                        guild.categories
                    )
                    if category:
                        channel = discord.utils.find(
                            lambda c: c.name.lower() == "봇",
                            category.channels
                        )
                        if channel:
                            # 채널별 권한 확인
                            channel_perms = channel.permissions_for(bot_member)
                            print(f"\n채널 '{channel.name}'에서의 봇 권한:")
                            print(f"메시지 보내기: {channel_perms.send_messages}")
                            print(f"파일 첨부: {channel_perms.attach_files}")
                            print(f"임베드 링크: {channel_perms.embed_links}")

                            if channel_perms.send_messages:
                                await channel.send("📢 이번 주 썬데이메이플 정보입니다!")
                                await 썬데이메이플(channel)
                            else:
                                print(f"봇이 채널에 메시지를 보낼 권한이 없습니다.")
                except Exception as e:
                    print(f"Guild {guild.name} 처리 중 오류 발생: {str(e)}")
                    continue
    except Exception as e:
        print(f"썬데이메이플_자동알림 실행 중 오류 발생: {str(e)}")


@썬데이메이플_자동알림.before_loop
async def before_썬데이메이플_자동알림():
    print("썬데이메이플 자동 알림이 시작되었습니다.")
    await bot.wait_until_ready()


@bot.command()
async def 도움말(ctx):
    """
    봇 명령어 도움말을 보여줍니다.
    """
    embed = discord.Embed(
        title="메이플스토리 봇 도움말",
        description="캐릭터의 정보와 경험치를 조회하는 봇입니다.",
        color=0x00ff00
    )

    # 기본 정보 명령어
    embed.add_field(
        name="!정보 [캐릭터명]",
        value="캐릭터의 기본 정보를 조회합니다.\n(레벨, 직업, 길드, 성별, 월드 등)",
        inline=False
    )

    # 경험치 그래프 명령어
    embed.add_field(
        name="!주간 [캐릭터명]",
        value="최근 7일간의 경험치와 레벨 변화를 그래프로 보여줍니다.",
        inline=False
    )

    # 월간 경험치 히트맵 명령어
    embed.add_field(
        name="!월간 [캐릭터명] [연도] [월]",
        value=("월간 경험치 획득량을 달력 형태로 보여줍니다.\n"
               "연도와 월을 생략하면 현재 월의 데이터를 보여줍니다.\n"
               "예시: !monthly 캐릭터명 2024 3"),
        inline=False
    )

    # 환산 명령어
    embed.add_field(
        name="!환산 [캐릭터명]",
        value=("메이플스카우터에서 캐릭터의 환산 정보를 확인할 수 있는 링크를 제공합니다.\n"
               "사이트맵을 보려면: !환산 사이트맵"),
        inline=False
    )

    # 썬데이메이플 명령어
    embed.add_field(
        name="!썬데이메이플",
        value=("현재 진행 중인 썬데이메이플 이벤트 정보를 보여줍니다.\n"
               "매주 금요일 오전 10시 1분에 자동으로 알림이 전송됩니다."),
        inline=False
    )

    # 푸터에 추가 정보
    embed.set_footer(text="데이터 출처: 메이플스토리 OpenAPI | 메이플스카우터")

    await ctx.send(embed=embed)


if __name__ == "__main__":
    if DISCORD_BOT_TOKEN is None:
        print("Error: DISCORD_BOT_TOKEN is not set")
        exit(1)
    bot.run(DISCORD_BOT_TOKEN)
