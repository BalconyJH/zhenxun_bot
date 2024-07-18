from asyncio.exceptions import TimeoutError

from nonebot.adapters import Bot
from nonebot.plugin import PluginMetadata
from nonebot_plugin_alconna import Alconna, Args, Arparma, Match, on_alconna
from nonebot_plugin_saa import Image, MessageFactory, Text
from nonebot_plugin_session import EventSession

from zhenxun.configs.config import Config
from zhenxun.configs.path_config import IMAGE_PATH, TEMP_PATH
from zhenxun.configs.utils import PluginExtraData
from zhenxun.services.log import logger
from zhenxun.utils.http_utils import AsyncHttpx
from zhenxun.utils.utils import change_pixiv_image_links
from zhenxun.utils.withdraw_manage import WithdrawManager

__plugin_meta__ = PluginMetadata(
    name="pid搜索",
    description="通过 pid 搜索图片",
    usage="""
    usage：
        通过 pid 搜索图片
        指令：
            p搜 [pid]
    """.strip(),
    extra=PluginExtraData(author="HibiKier", version="0.1").dict(),
)


headers = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.6;"
    " rv:2.0.1) Gecko/20100101 Firefox/4.0.1",
    "Referer": "https://www.pixiv.net",
}

_matcher = on_alconna(
    Alconna("p搜", Args["pid", int]), aliases={"P搜"}, priority=5, block=True
)


@_matcher.handle()
async def _(pid: Match[int]):
    if pid.available:
        _matcher.set_path_arg("pid", pid.result)


@_matcher.got_path("pid", prompt="需要查询的图片PID是？")
async def _(bot: Bot, session: EventSession, arparma: Arparma, pid: int):
    url = Config.get_config("hibiapi", "HIBIAPI") + "/api/pixiv/illust"
    if pid in ["取消", "算了"]:
        await Text("已取消操作...").finish()
    for _ in range(3):
        try:
            data = (
                await AsyncHttpx.get(
                    url,
                    params={"id": pid},
                    timeout=5,
                )
            ).json()
        except TimeoutError:
            pass
        except Exception as e:
            await Text(f"发生了一些错误..{type(e)}：{e}").finish()
        else:
            if data.get("error"):
                await Text(data["error"]["user_message"]).finish(reply=True)
            data = data["illust"]
            if not data["width"] and not data["height"]:
                await Text(f"没有搜索到 PID：{pid} 的图片").finish(reply=True)
            pid = data["id"]
            title = data["title"]
            author = data["user"]["name"]
            author_id = data["user"]["id"]
            image_list = []
            try:
                image_list.append(data["meta_single_page"]["original_image_url"])
            except KeyError:
                for image_url in data["meta_pages"]:
                    image_list.append(image_url["image_urls"]["original"])
            for i, img_url in enumerate(image_list):
                img_url = change_pixiv_image_links(img_url)
                if not await AsyncHttpx.download_file(
                    img_url,
                    TEMP_PATH / f"pid_search_{session.id1}_{i}.png",
                    headers=headers,
                ):
                    await Text("图片下载失败了...").finish(reply=True)
                tmp = ""
                if session.id3 or session.id2:
                    tmp = "\n【注】将在30后撤回......"
                receipt = await MessageFactory(
                    [
                        Text(
                            f"title：{title}\n"
                            f"pid：{pid}\n"
                            f"author：{author}\n"
                            f"author_id：{author_id}\n"
                        ),
                        Image(TEMP_PATH / f"pid_search_{session.id1}_{i}.png"),
                        Text(f"{tmp}"),
                    ]
                ).send()
                logger.info(
                    f" 查询图片 PID：{pid}", arparma.header_result, session=session
                )
                if session.id3 or session.id2:
                    await WithdrawManager.withdraw_message(
                        bot, receipt.extract_message_id().message_id, 30  # type: ignore
                    )
            break
    else:
        await Text("图片下载失败了...").send(reply=True)