(function () {
    function buildTeamsUrls(email) {
        const cleanEmail = String(email || '').trim();
        if (!cleanEmail) return null;
        const encodedEmail = encodeURIComponent(cleanEmail);
        return {
            webUrl: `https://teams.microsoft.com/l/chat/0/0?users=${encodedEmail}`,
            appUrl: `msteams://teams.microsoft.com/l/chat/0/0?users=${encodedEmail}`,
        };
    }

    function abrirTeams(email) {
        const urls = buildTeamsUrls(email);
        if (!urls) return;

        let fallbackTriggered = false;
        let fallbackTimer = null;

        const cleanup = function () {
            if (fallbackTimer) {
                window.clearTimeout(fallbackTimer);
                fallbackTimer = null;
            }
            window.removeEventListener('blur', handleSuccessSignal);
            document.removeEventListener('visibilitychange', handleVisibilityChange);
            window.removeEventListener('pagehide', handleSuccessSignal);
        };

        const handleSuccessSignal = function () {
            fallbackTriggered = true;
            cleanup();
        };

        const handleVisibilityChange = function () {
            if (document.hidden) {
                handleSuccessSignal();
            }
        };

        window.addEventListener('blur', handleSuccessSignal, { once: true });
        document.addEventListener('visibilitychange', handleVisibilityChange);
        window.addEventListener('pagehide', handleSuccessSignal, { once: true });

        fallbackTimer = window.setTimeout(function () {
            cleanup();
            if (!fallbackTriggered) {
                window.open(urls.webUrl, '_blank', 'noopener');
            }
        }, 1200);

        window.location.href = urls.appUrl;
    }

    window.abrirTeams = abrirTeams;
})();
