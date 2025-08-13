
from typing import Optional, Union
import aiohttp
from astrbot.api.star import Context, Star, register
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.core.message.components import Image
from astrbot.core.message.message_event_result import MessageChain
from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import (
    AiocqhttpMessageEvent,
)
from astrbot.api.event import filter
from astrbot.api import logger

@register(
    "astrbot_plugin_image_summary",
    "Zhalslar",
    "图片外显插件",
    "v1.0.0",
)
class ImageSummaryPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.group_whitelist = config.get("group_whitelist", [])
        self.default_summary = config.get("default_summary", "测试")
        self.yiyan_urls = config.get("yiyan_urls", [])

    @filter.on_decorating_result()
    async def on_recall(self, event: AiocqhttpMessageEvent):
        """监听消息进行图片外显"""
        # 白名单群
        group_id = event.get_group_id()
        if self.group_whitelist and group_id not in self.group_whitelist:
            return

        chain = event.get_result().chain

        # 仅考虑图片消息
        if not any(isinstance(seg, Image) for seg in chain):
            return

        # 注入summary
        obmsg: list[dict] = await event._parse_onebot_json(MessageChain(chain))
        obmsg[0]["data"]["summary"] = await self.get_summary()

        # 发送消息
        await event.bot.send(event.message_obj.raw_message, obmsg) # type: ignore

        # 清空原消息链
        chain.clear()
        event.stop_event()


    async def get_summary(self):
        """获取外显文本"""
        params = None
        text = await self._make_request(urls=self.yiyan_urls, params=params)
        summary = text[:20] if text else self.default_summary
        return summary

    async def _make_request(
        self, urls: list, params: Optional[dict] = None
    ) -> Union[bytes, str, dict, None]:
        """
        发送GET请求
        :param url: 请求的URL地址
        :param params: 请求参数，默认为None
        :return: 响应对象或None
        """
        for u in urls:
            async with aiohttp.ClientSession() as session:
                for u in urls:
                    try:
                        async with session.get(
                            url=u, params=params, timeout=30
                        ) as response:
                            response.raise_for_status()
                            content_type = response.headers.get(
                                "Content-Type", ""
                            ).lower()
                            if "application/json" in content_type:
                                return await response.json()
                            elif (
                                "text/html" in content_type
                                or "text/plain" in content_type
                            ):
                                return (await response.text()).strip()
                            else:
                                return await response.read()
                    except Exception as e:
                        logger.warning(f"请求 URL 失败: {u}, 错误: {e}")
                        continue  # 尝试下一个 URL
