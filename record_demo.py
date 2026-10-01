import asyncio
import glob
import os
import subprocess
from playwright.async_api import async_playwright

async def record_demo():
    output_dir = "/config/Desktop/Session1/demo_raw"
    os.makedirs(output_dir, exist_ok=True)

    # Clean old webm files
    for old_file in glob.glob(os.path.join(output_dir, "*.webm")):
        try:
            os.remove(old_file)
        except Exception:
            pass

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 720},
            record_video_dir=output_dir,
            record_video_size={"width": 1280, "height": 720}
        )

        page = await context.new_page()
        
        print("Navigating to Travel Concierge frontend...")
        await page.goto("http://localhost:8080/")
        await page.wait_for_timeout(3000)

        # Prompt 1: Click the first example chip button (.chip)
        print("Clicking first prompt chip...")
        chips = await page.query_selector_all(".chip")
        if chips and len(chips) > 0:
            await chips[0].click()
        else:
            print("Fallback typing into #input...")
            await page.fill("#input", "Plan a 3-day itinerary in Paris with luxury hotels")
            await page.keyboard.press("Enter")

        print("Waiting for agent to respond to Prompt 1...")
        # Wait up to 20 seconds for agent bubble to complete (no longer '…')
        await page.wait_for_timeout(18000)

        # Prompt 2: Richer prompt showing tool call & image generation
        print("Typing Prompt 2 into #input (postcard image & weather tool call)...")
        await page.fill("#input", "Generate a postcard image of the Eiffel Tower and check the live weather in Paris.")
        await page.wait_for_timeout(1000)
        await page.keyboard.press("Enter")

        print("Waiting for agent to respond to Prompt 2...")
        await page.wait_for_timeout(22000)

        print("Recording complete, closing browser context...")
        await page.wait_for_timeout(2000)
        await context.close()
        await browser.close()

    print("Browser closed. Locating recorded webm video...")
    webm_files = glob.glob(os.path.join(output_dir, "*.webm"))
    if not webm_files:
        raise RuntimeError("No raw webm video file found!")

    raw_video = webm_files[0]
    print(f"Raw video file: {raw_video}")

    music_file = "/config/Desktop/Session1/lofi_beat.wav"
    artifact_dir = "/config/.gemini/antigravity/brain/f9784c95-52ad-49a8-ac8b-e14be6b72bc0"
    os.makedirs(artifact_dir, exist_ok=True)
    final_video = os.path.join(artifact_dir, "travel_concierge_demo.mp4")

    # Combine video and audio with ffmpeg
    cmd = [
        "ffmpeg", "-y",
        "-i", raw_video,
        "-i", music_file,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "22",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        final_video
    ]
    print("Combining video with upbeat lo-fi background music...")
    subprocess.run(cmd, check=True)
    print(f"Demo video created successfully at: {final_video}")

if __name__ == "__main__":
    asyncio.run(record_demo())
