"""
Message Catalog — every user-facing string as per spec.
All references to [Mobile No] are replaced at runtime with settings.SUPPORT_MOBILE.
"""
from app.config import settings

M = settings.SUPPORT_MOBILE   # shorthand


def thank_you_close() -> str:
    return "Thank you for your response."


def generic_thank_you() -> str:
    return f"Thank you for your reply. If any issues, please contact {M}."


def stage1_issue_noted() -> str:
    return (
        f"Your issue has been noted. Our team will connect with you shortly. "
        f"If there is urgency, please contact {M}."
    )


def stage1_unresolved_issue(last_issue: str) -> str:
    return (
        f"Our team is working to resolve your issue. "
        f"If urgency, please contact {M}."
    )


def stage23_issue_noted() -> str:
    return (
        f"Your issue has been noted. Team will work on it. "
        f"If any urgency, please contact {M}."
    )


def pod_instruction_no_charges() -> str:
    return f"Please WhatsApp the POD copy at {M}."


def pod_instruction_with_charges() -> str:
    return (
        f"Make sure the charges are mentioned correctly on the POD with seal and sign "
        f"and WhatsApp the POD copy at {M}."
    )


def pod_no_seal_warning() -> str:
    return (
        f"Without seal and sign the unloading charges will not be reimbursed. "
        f"Please get it written on POD and WhatsApp the POD copy at {M}."
    )


def stage4_pod_seal_warning_no_charges() -> str:
    return (
        f"Thank you for your reply. Make sure the seal and sign is of the correct party on POD. "
        f"If there is no seal / wrong seal, then balance amount will not be paid. "
        f"If any issues, please contact {M}."
    )


# ── Questions ─────────────────────────────────────────────────────────────────

def ask_driver_confirmation(vehicle_no: str, from_loc: str, to_loc: str) -> str:
    return (
        f"Are you the driver for vehicle *{vehicle_no}* travelling from "
        f"*{from_loc}* to *{to_loc}*?"
    )


def ask_current_location() -> str:
    return "What is your current location? (Please type your location)"


def ask_difficulty() -> str:
    return "Are you facing any difficulty in reaching the destination?"


def ask_s1_issue_resolved(last_issue: str) -> str:
    return f"Last time you faced: _{last_issue}_\nIs this issue resolved?"


def ask_s2_issue_existing(last_issue: str) -> str:
    return f"Are you still facing the issue: _{last_issue}_?"


def ask_s2_new_issue() -> str:
    return "Are you facing any new issue?"


def ask_s2_issue_yn() -> str:
    return "Are you facing any issues at unloading point?"


def ask_s2_select_issue() -> str:
    return "Please select the issue you are facing:"


def ask_s3_issue() -> str:
    return "Are you facing any issue while unloading?"


def ask_s4_unloading_time() -> str:
    return "Please select Unloading complete date and time:"


def ask_s2_report_time() -> str:
    return "Please select Unloading point report time:"


def ask_charges_yn() -> str:
    return "Is the party/labor asking for unloading charges more than INR 100?"


def ask_charges_amount() -> str:
    return "What charges did you pay? (Please enter numeric amount only)"


def invalid_amount() -> str:
    return "Please enter charges in number only."


def ask_s5_confirm_no_charges() -> str:
    return "You had confirmed no unloading charges were paid more than INR 100. Is that correct?"


def ask_s5_confirm_with_charges(amount: float) -> str:
    return f"You had mentioned the unloading charges paid were INR {amount:.0f}. Is this correct?"


def ask_corrected_amount() -> str:
    return "Please enter the corrected unloading charges amount (numeric only):"


def ask_charges_on_pod() -> str:
    return "Are the charges mentioned on the POD with seal and sign?"


MAIN_MENU_BODY = (
    "Please select your current status for this load:"
)

MAIN_MENU_SECTIONS = [
    {
        "title": "Load Status",
        "rows": [
            {"id": "stage_1", "title": "1. Enroute", "description": "I am enroute to destination"},
            {"id": "stage_2", "title": "2. Reached unloading", "description": "Reached unloading point, not started"},
            {"id": "stage_3", "title": "3. Unloading started", "description": "Vehicle unloading has started"},
            {"id": "stage_4", "title": "4. Unloaded, no POD", "description": "Unloaded, POD not received"},
            {"id": "stage_5", "title": "5. Unloaded + POD", "description": "Unloaded and POD received"},
        ],
    }
]
