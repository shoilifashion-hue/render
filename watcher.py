import asyncio
import logging
import os
import httpx

# --- পরিবেশ ভ্যারিয়েবল থেকে তথ্য নেওয়া ---
GITHUB_TOKEN = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GH_REPO", "shoilifashion-hue/STC-Sports")
EVENT_TYPE = os.getenv("EVENT_TYPE", "source_updated")
WORKFLOW_FILE = os.getenv("WORKFLOW_FILE", "update.yml")
BRANCH = os.getenv("BRANCH", "main")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("RENDER_WATCHER")


async def trigger_github_action():
    """রেন্ডার থেকে গিটহাব অ্যাকশন ট্রিগার করার ফাংশন"""
    if not GITHUB_TOKEN or not GITHUB_REPO:
        log.error("GitHub PAT or REPO not found in Environment Variables!")
        return False

    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Render-Watcher-Bot",
    }

    triggered = False

    async with httpx.AsyncClient() as client:
        # মেথড ১: repository_dispatch
        try:
            disp_url = f"https://api.github.com/repos/{GITHUB_REPO}/dispatches"
            payload = {"event_type": EVENT_TYPE}
            resp = await client.post(disp_url, json=payload, headers=headers, timeout=12.0)
            if resp.status_code == 204:
                log.info(f">>> SUCCESS: Triggered via repository_dispatch ({EVENT_TYPE})")
                triggered = True
        except Exception as e:
            log.warning(f"repository_dispatch error: {e}")

        # মেথড ২: workflow_dispatch (ব্যাকআপ হিসেবে সরাসরি ফাইল ট্রিগার)
        if not triggered:
            try:
                wf_url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/workflows/{WORKFLOW_FILE}/dispatches"
                wf_payload = {"ref": BRANCH}
                resp2 = await client.post(wf_url, json=wf_payload, headers=headers, timeout=12.0)
                if resp2.status_code in [204, 200]:
                    log.info(f">>> SUCCESS: Triggered via workflow_dispatch ({WORKFLOW_FILE})")
                    triggered = True
            except Exception as e:
                log.warning(f"workflow_dispatch error: {e}")

    return triggered


async def monitor_loop():
    """প্রতি ১৫ মিনিট (৯০০ সেকেন্ড) পর পর ট্রিগার পাঠানোর মূল লুপ"""
    log.info("Watcher started. Will trigger GitHub Actions every 15 minutes...")
    while True:
        log.info("Sending trigger signal to GitHub Actions...")
        await trigger_github_action()
        # ১৫ মিনিট (৯০০ সেকেন্ড) অপেক্ষা
        await asyncio.sleep(900)


async def run_render_server():
    """রেন্ডারের ফ্রি পোর্ট সচল রাখার জন্য ডামি সার্ভার (স্লিপিং প্রতিরোধ করতে)"""
    port = int(os.getenv("PORT", 8080))

    async def handle_client(reader, writer):
        response = b"HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\nConnection: close\r\n\r\nOK"
        writer.write(response)
        await writer.drain()
        writer.close()

    server = await asyncio.start_server(handle_client, "0.0.0.0", port)
    log.info(f"Health check server listening on port {port}")
    async with server:
        await server.serve_forever()


async def main():
    await asyncio.gather(
        monitor_loop(),
        run_render_server(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        log.info("Watcher stopped.")
