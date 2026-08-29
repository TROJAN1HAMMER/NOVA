"""
NOVA CLI Demo Reset Command
Run via: python -m app.demo.reset
"""

import sys
from app.demo.orchestrator import demo_orchestrator


def main():
    print("=" * 65)
    print("NOVA — RESETTING CANONICAL DEMONSTRATION ENVIRONMENT")
    print("=" * 65)

    result = demo_orchestrator.reset_demo_environment()

    print(f"Status        : {result['status']}")
    print(f"Demo State    : {result['demo_state']}")
    print(f"Target Scope  : {result['target_scope']}")
    print(f"Posture Score : {result['vulnerable_analysis']['posture_score']:.1f} / 100")
    print(f"Posture Rating: {result['vulnerable_analysis']['posture_rating']}")
    print("=" * 65)
    print("DEMO ENVIRONMENT RESET CLEANLY TO VULNERABLE BASELINE (STATE A).")
    print("=" * 65)


if __name__ == "__main__":
    main()
