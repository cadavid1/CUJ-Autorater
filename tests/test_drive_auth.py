"""
Quick diagnostic script for Google Drive OAuth issues
Run this to check your OAuth configuration
"""

import streamlit as st
from drive_client import DriveClient

def main():
    st.title("🔍 Drive OAuth Diagnostic")

    st.write("### Current Configuration")

    try:
        client_id = st.secrets["google_drive"]["client_id"]
        client_secret = st.secrets["google_drive"]["client_secret"]
        redirect_uri = DriveClient.get_redirect_uri()

        st.write(f"**Client ID:** {client_id}")
        st.write(f"**Client Secret:** {'*' * len(client_secret[:-4]) + client_secret[-4:]}")
        st.write(f"**Redirect URI:** {redirect_uri}")

        st.write("### ✅ Configuration Checklist")
        st.markdown("""
        Please verify in [Google Cloud Console](https://console.cloud.google.com/apis/credentials):

        1. **OAuth Client Type** must be **"Web application"** (NOT Desktop)
        2. **Authorized redirect URIs** must include: `http://localhost:8501`
        3. **Client ID** matches: `{}`
        4. **APIs Enabled**:
           - Google Drive API
           - (Optional) Google Picker API
        5. **OAuth consent screen** is configured
        """.format(client_id))

        st.write("### 🧪 Test OAuth Flow")

        if st.button("Generate Auth URL"):
            try:
                flow, auth_url = DriveClient.get_auth_url()
                st.success("✅ OAuth flow created successfully!")
                st.markdown(f"**Test URL:** {auth_url}")
                st.info("If clicking this link fails with 'redirect_uri_mismatch' or 'invalid_client', check your Google Cloud Console settings.")
            except Exception as e:
                st.error(f"❌ Failed to create OAuth flow: {e}")
                st.write("This error suggests an issue with your secrets configuration.")

    except KeyError as e:
        st.error(f"❌ Missing configuration: {e}")
        st.write("Check your `.streamlit/secrets.toml` file")
    except Exception as e:
        st.error(f"❌ Error: {e}")

if __name__ == "__main__":
    main()
