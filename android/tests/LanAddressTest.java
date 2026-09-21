import app.splatreplay.android.LanAddress;

public final class LanAddressTest {
    public static void main(String[] args) {
        assert LanAddress.normalize("http://192.168.1.10:8000").equals("http://192.168.1.10:8000/");
        assert LanAddress.sameOrigin("http://192.168.1.10/", "http://192.168.1.10:80/api/health");
        assert !LanAddress.sameOrigin("http://192.168.1.10/", "http://192.168.1.10.evil.example/");
        for (String bad : new String[] { "http://127.0.0.1", "http://8.8.8.8", "file:///etc/passwd",
                "http://192.168.1.1@evil.example", "http://192.168.1.1:65536", "http://192.168.1.1/a",
                "http://192.168.1.1?x=1", "http://192.168.01.1", "http://172.32.1.1", "http://10.0.0.256" }) {
            boolean rejected = false;
            try { LanAddress.normalize(bad); } catch (IllegalArgumentException expected) { rejected = true; }
            assert rejected : bad;
        }
        System.out.println("LAN address checks passed");
    }
}
