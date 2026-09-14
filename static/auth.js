"use strict";

// Explicit ArrayBuffer conversion also works on Safari versions without JSON helpers.
function decodeBase64url(value) {
    const encoded = value.replace(/-/g, "+").replace(/_/g, "/");
    return Uint8Array.from(atob(encoded + "=".repeat((4 - encoded.length % 4) % 4)), c => c.charCodeAt(0));
}
function encodeBase64url(value) {
    return btoa(String.fromCharCode(...new Uint8Array(value)))
        .replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

const passkeyButton = document.getElementById("passkey-button");
if (passkeyButton) {
    passkeyButton.addEventListener("click", async () => {
        const message = document.getElementById("auth-message");
        const registering = passkeyButton.dataset.mode === "register";
        passkeyButton.disabled = true;
        message.textContent = "端末の本人確認を進めてください。";
        try {
            if (!window.isSecureContext || !navigator.credentials || !window.PublicKeyCredential) {
                throw new Error("HTTPSでパスキーに対応したブラウザを使用してください。");
            }
            async function post(url, body) {
                const response = await fetch(url, {
                    method: "POST", credentials: "same-origin",
                    headers: {"Content-Type": "application/json", "X-CSRF-Token": document.querySelector('meta[name="csrf-token"]').content},
                    body: JSON.stringify(body || {})
                });
                if (!response.ok) {
                    let error = "操作をやり直してください。必要ならページを再読み込みしてください。";
                    if (response.headers.get("content-type")?.includes("application/json")) {
                        error = (await response.json()).error || error;
                    }
                    throw new Error(error);
                }
                return response.json();
            }
            const publicKey = await post(passkeyButton.dataset.optionsUrl);
            publicKey.challenge = decodeBase64url(publicKey.challenge);
            if (registering) publicKey.user.id = decodeBase64url(publicKey.user.id);
            for (const key of ["allowCredentials", "excludeCredentials"]) {
                if (publicKey[key]) publicKey[key] = publicKey[key].map(item => ({...item, id: decodeBase64url(item.id)}));
            }
            const credential = registering
                ? await navigator.credentials.create({publicKey})
                : await navigator.credentials.get({publicKey});
            if (!credential) throw new Error("本人確認が完了しませんでした。");
            const response = {clientDataJSON: encodeBase64url(credential.response.clientDataJSON)};
            if (registering) {
                response.attestationObject = encodeBase64url(credential.response.attestationObject);
                response.transports = credential.response.getTransports?.() || [];
            } else {
                response.authenticatorData = encodeBase64url(credential.response.authenticatorData);
                response.signature = encodeBase64url(credential.response.signature);
                response.userHandle = credential.response.userHandle ? encodeBase64url(credential.response.userHandle) : null;
            }
            const result = await post(passkeyButton.dataset.verifyUrl, {
                id: credential.id, rawId: encodeBase64url(credential.rawId), type: credential.type, response
            });
            window.location.assign(result.redirect);
        } catch (error) {
            message.textContent = error.name === "NotAllowedError"
                ? "本人確認がキャンセルされたか、時間切れになりました。もう一度お試しください。"
                : error.name === "Error" ? error.message : "パスキーを利用できませんでした。ページを再読み込みしてお試しください。";
        } finally {
            passkeyButton.disabled = false;
        }
    });
}
