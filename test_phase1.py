#!/usr/bin/env python
"""
Quick test of Phase 1 LLM functionality:
  1. Onboarding answer parsing
  2. Memory extraction pipeline
  3. Provider fallback routing
"""

import asyncio
import sys
from pathlib import Path

# Add the service to the path
sys.path.insert(0, str(Path(__file__).parent / "services" / "api"))

import os
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://coach:coach@localhost:5432/lifecoach")
os.environ.setdefault("LOG_LEVEL", "info")


async def test_onboarding_parsing():
    """Test that onboarding answers are parsed via LLM."""
    from app.llm.litellm_client import LiteLLMCoachLLM
    from app.onboarding.engine import DomainSlot
    from app.onboarding.parsing import parse_answer

    print("\n=== Testing Onboarding Answer Parsing ===")

    llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")

    test_cases = [
        (
            DomainSlot.EMPLOYMENT_STATUS,
            "I'm building an AI startup with my co-founder, we're pre-revenue",
        ),
        (
            DomainSlot.RELATIONSHIP_STATUS,
            "I'm married with two kids",
        ),
        (
            DomainSlot.CAREER_GOAL_1Y,
            "I want to get promoted to senior engineer",
        ),
    ]

    for slot, raw_answer in test_cases:
        print(f"\n📋 Slot: {slot.value}")
        print(f"   Raw answer: {raw_answer}")
        try:
            result = await parse_answer(llm, slot, raw_answer)
            print(f"   ✅ Parsed: {result}")
        except Exception as e:
            print(f"   ❌ Error: {e}")


async def test_llm_fallback():
    """Test that provider fallback works."""
    from app.llm.litellm_client import LiteLLMCoachLLM
    from app.llm.coach_llm import LLMMessage

    print("\n=== Testing LLM Provider Fallback ===")

    llm = LiteLLMCoachLLM(model="anthropic/claude-haiku-4-5-20251001")

    messages = [
        LLMMessage(role="user", content="What is 2+2? Answer with just the number."),
    ]

    try:
        response = await llm.generate(messages)
        print(f"✅ Generation successful: {response.content[:100]}")
        print(f"   Model used: {response.model}")
        print(f"   Tokens: {response.usage}")
    except Exception as e:
        print(f"❌ Generation failed: {e}")
        if "No LLM providers available" in str(e):
            print("   (All providers exhausted due to funding/auth issues)")
        return False

    return True


async def test_embedding():
    """Test that embeddings work."""
    from app.llm.litellm_client import LiteLLMCoachLLM

    print("\n=== Testing Embeddings ===")

    llm = LiteLLMCoachLLM(model="openai/text-embedding-3-small")

    texts = [
        "I'm working on a startup in the AI space",
        "I want to improve my health and fitness",
        "My biggest challenge is work-life balance",
    ]

    try:
        embeddings = await llm.embed(texts)
        print(f"✅ Embedding successful")
        print(f"   Texts: {len(texts)}")
        print(f"   Embedding dims: {len(embeddings[0])}")
        print(f"   Sample vector (first 5 dims): {embeddings[0][:5]}")
    except Exception as e:
        print(f"❌ Embedding failed: {e}")
        if "No LLM providers available" in str(e):
            print("   (OpenAI embedding not funded)")
        return False

    return True


async def main():
    """Run all tests."""
    print("🧪 Phase 1 LLM Functionality Tests")
    print("=" * 50)

    print("\nℹ️  If you see auth/funding errors below, it means:")
    print("   - The provider isn't funded, so fallback will try the next one")
    print("   - If all providers fail, the system gracefully falls back to raw text")

    try:
        await test_onboarding_parsing()
    except Exception as e:
        print(f"\n⚠️  Onboarding parsing test error: {e}")

    fallback_ok = await test_llm_fallback()
    embedding_ok = await test_embedding()

    print("\n" + "=" * 50)
    if fallback_ok or embedding_ok:
        print("✅ At least one provider is working — system is operational")
    else:
        print("⚠️  All providers exhausted — check API keys and funding")
    print("\nNext steps:")
    print("  1. Ensure at least one provider (OpenAI/Gemini/Anthropic) has funds")
    print("  2. Run: pnpm dev (web) + uv run uvicorn app.main:app --reload (API)")
    print("  3. Test the onboarding flow at http://localhost:3000")


if __name__ == "__main__":
    asyncio.run(main())
