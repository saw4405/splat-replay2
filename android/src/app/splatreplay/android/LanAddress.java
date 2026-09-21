package app.splatreplay.android;

import java.net.URI;

/** DNS を使わず、自宅 LAN の IPv4 接続先を検証する。認証機構ではない。 */
public final class LanAddress {
    private LanAddress() {}

    public static String normalize(String text) {
        try {
            URI uri = new URI(text.trim());
            String scheme = uri.getScheme();
            String host = uri.getHost();
            int port = uri.getPort();
            if (!("http".equals(scheme) || "https".equals(scheme)) || host == null
                    || uri.getUserInfo() != null || uri.getQuery() != null || uri.getFragment() != null
                    || !(uri.getPath().isEmpty() || "/".equals(uri.getPath()))
                    || port == 0 || port > 65535 || port < -1) throw new IllegalArgumentException();
            String[] parts = host.split("\\.", -1);
            if (parts.length != 4) throw new IllegalArgumentException();
            int[] octets = new int[4];
            for (int i = 0; i < 4; i++) {
                if (!parts[i].matches("0|[1-9][0-9]{0,2}")) throw new IllegalArgumentException();
                octets[i] = Integer.parseInt(parts[i]);
                if (octets[i] > 255) throw new IllegalArgumentException();
            }
            if (!(octets[0] == 10 || (octets[0] == 172 && octets[1] >= 16 && octets[1] <= 31)
                    || (octets[0] == 192 && octets[1] == 168))) throw new IllegalArgumentException();
            return scheme + "://" + host + (port == -1 ? "" : ":" + port) + "/";
        } catch (Exception error) {
            throw new IllegalArgumentException("自宅LANのURLを入力してください（例: http://192.168.1.10:8000）", error);
        }
    }

    public static boolean sameOrigin(String base, String target) {
        try {
            URI a = new URI(base), b = new URI(target);
            return a.getScheme().equals(b.getScheme()) && a.getHost().equals(b.getHost())
                    && effectivePort(a) == effectivePort(b) && b.getUserInfo() == null;
        } catch (Exception error) { return false; }
    }

    private static int effectivePort(URI uri) {
        return uri.getPort() == -1 ? ("https".equals(uri.getScheme()) ? 443 : 80) : uri.getPort();
    }
}
