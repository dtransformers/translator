import httpx

class DocumentService:
    @staticmethod
    async def download_json(url: str) -> dict:
        """Download JSON document data from a URL using httpx."""
        async with httpx.AsyncClient() as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
