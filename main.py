
import random
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

    async def initialize(self):
        self.session = aiohttp.ClientSession()

    @filter.on_decorating_result()
    async def on_image_summary(self, event: AiocqhttpMessageEvent):
        """监听消息进行图片外显"""
        # 白名单群
        group_id = event.get_group_id()
        if self.group_whitelist and group_id not in self.group_whitelist:
            return

        chain = event.get_result().chain

        # 仅考虑单张图片消息
        if chain and len(chain)==1 and isinstance(chain[0], Image):
            # 注入summary
            obmsg: list[dict] = await event._parse_onebot_json(MessageChain(chain))
            obmsg[0]["data"]["summary"] = await self.get_summary()
            # 发送消息
            await event.bot.send(event.message_obj.raw_message, obmsg) # type: ignore
            # 清空原消息链
            chain.clear()
            event.stop_event()


    async def get_summary(self, max_len=20):
        """获取外显文本, 过长则截断"""
        res = await self._make_request(urls=self.yiyan_urls)
        if isinstance(res, str):
            summary = res[:max_len]
        else:
            summary = self.default_summary
        return summary



    async def _make_request(self, urls: list[str]) -> str | None:
        """
        随机顺序尝试所有 URL，直到拿到「可当作文本」的内容。
        如果返回 JSON，尝试取其中 'content' 或 'text' 字段；若拿不到，继续换下一个 URL。
        如果返回纯文本，直接返回。
        其余情况视为失败，继续重试。
        """
        if not urls:
            return None

        # 随机打乱顺序，避免每次都打到第一个
        for url in random.sample(urls, k=len(urls)):
            try:
                async with self.session.get(url, timeout=30) as resp:
                    resp.raise_for_status()
                    ctype = resp.headers.get("Content-Type", "").lower()

                    if "application/json" in ctype:
                        data = await resp.json()
                        # 兼容常见字段
                        text = (
                            data.get("content")
                            or data.get("text")
                            or data.get("msg")
                            or str(data)  # 兜底
                        )
                        if text and isinstance(text, str):
                            return text.strip()

                    elif "text/html" in ctype or "text/plain" in ctype:
                        return (await resp.text()).strip()

                    # 其余类型直接跳过
                    logger.warning(f"{url} 返回非文本类型，跳过")
                    continue

            except Exception as e:
                logger.warning(f"请求 URL 失败: {url}, 错误: {e}")
                continue

        logger.error("所有 yiyan_urls 均未能获取到可用文本")
        return None
