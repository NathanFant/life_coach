#!/usr/bin/env python
"""
Test LLM functionality without database.
"""

import asyncio
import sys
from pathlib import Path
import os

# Add the service to the path
sys.path.insert(0, str(Path(__file__).parent / "services" / "api"))

# Load .env.local manually
env_path = Path(__file__).parent / ".env.local"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


async def test_llm_generation():
    """Test basic LLM generation with fallback."""
    from app.llm.litellm_client import LiteLLMCoachLLM
    from app.llm.coach_llm import LLMMessage

    print("\n=== Testing LLM Generation with Fallback ===")

    llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")

    messages = [
        LLMMessage(role="user", content="You are a life coach. Summarize these life goals in one sentence: 'Build a successful AI startup, improve health, strengthen family relationships'"),
    ]

    print("Attempting to generate coaching guidance...")
    try:
        response = await llm.generate(messages)
        print(f"\n✅ Generation successful!")
        print(f"   Model used: {response.model}")
        print(f"   Response: {response.content}")
        print(f"   Tokens used: {response.usage}")
        return True
    except Exception as e:
        print(f"\n⚠️  Generation failed: {type(e).__name__}")
        print(f"   Error: {str(e)[:200]}")
        return False


async def test_onboarding_parsing():
    """Test onboarding answer parsing."""
    from app.llm.litellm_client import LiteLLMCoachLLM
    from app.onboarding.engine import DomainSlot
    from app.onboarding.parsing import parse_answer

    print("\n=== Testing Onboarding Answer Parsing ===")

    llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")

    # Test parsing an employment status answer
    raw_answer = "I'm building an AI startup with my co-founder. We're pre-revenue but growing fast."
    slot = DomainSlot.EMPLOYMENT_STATUS

    print(f"Raw answer: {raw_answer}")
    print(f"Slot: {slot.value}")
    print("\nParsing...")

    try:
        result = await parse_answer(llm, slot, raw_answer)
        print(f"\n✅ Parsing successful!")
        print(f"   Parsed structure: {result}")
        return True
    except Exception as e:
        print(f"\n⚠️  Parsing failed: {type(e).__name__}")
        print(f"   Error: {str(e)[:200]}")
        return False


async def test_embedding():
    """Test embeddings."""
    from app.llm.litellm_client import LiteLLMCoachLLM

    print("\n=== Testing Embeddings ===")

    llm = LiteLLMCoachLLM(model="openai/text-embedding-3-small")

    texts = [
        "I want to build a successful AI startup",
        "I want to improve my health and fitness",
    ]

    print(f"Embedding {len(texts)} texts...")
    try:
        embeddings = await llm.embed(texts)
        print(f"\n✅ Embedding successful!")
        print(f"   Dimensions: {len(embeddings[0])}")
        print(f"   Sample (first 5 values): {embeddings[0][:5]}")
        return True
    except Exception as e:
        print(f"\n⚠️  Embedding failed: {type(e).__name__}")
        print(f"   Error: {str(e)[:200]}")
        return False


async def main():
    """Run tests."""
    print("=" * 60)
    print("🧪 Phase 1 LLM Tests (No Database Required)")
    print("=" * 60)

    results = {}

    results["generation"] = await test_llm_generation()
    results["parsing"] = await test_onboarding_parsing()
    results["embedding"] = await test_embedding()

    print("\n" + "=" * 60)
    print("📊 Results Summary:")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅" if passed else "⚠️ "
        print(f"{status} {test_name.title()}: {'PASS' if passed else 'FAIL'}")

    if any(results.values()):
        print("\n✅ At least one provider is working — system operational!")
    else:
        print("\n❌ All providers unavailable — check API keys and funding")

    print("\n💡 If tests failed due to auth/funding:")
    print("   1. Verify API keys in .env.local")
    print("   2. Ensure at least one provider has active credits")
    print("   3. Check that keys match the correct provider")


if __name__ == "__main__":
    asyncio.run(main())
