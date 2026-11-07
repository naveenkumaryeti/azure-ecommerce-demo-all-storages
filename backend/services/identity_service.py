"""Azure AD / Entra ID authentication via DefaultAzureCredential.
On a VMSS instance it asks IMDS (169.254.169.254) for a token for the VM's managed identity.
Locally it falls back to `az login`. No keys, passwords or secrets anywhere."""
from azure.identity import DefaultAzureCredential
import config

_cred = None


def get_credential():
    global _cred
    if _cred is None:
        _cred = DefaultAzureCredential(managed_identity_client_id=config.MANAGED_IDENTITY_CLIENT_ID)
    return _cred


def token_status():
    """Used by the dashboard / health?deep=1 to prove an Entra token can be obtained."""
    try:
        t = get_credential().get_token("https://storage.azure.com/.default")
        return {"ok": True, "expires_on": t.expires_on}
    except Exception as e:  # noqa
        return {"ok": False, "error": str(e)[:300]}
