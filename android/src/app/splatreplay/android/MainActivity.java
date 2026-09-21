package app.splatreplay.android;

import android.app.Activity;
import android.app.AlertDialog;
import android.app.Dialog;
import android.content.Intent;
import android.content.res.ColorStateList;
import android.graphics.Color;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.os.Message;
import android.text.SpannableString;
import android.text.Spanned;
import android.text.style.ForegroundColorSpan;
import android.view.View;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceError;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.ScrollView;
import android.widget.Toast;
import java.net.HttpURLConnection;
import java.net.URL;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** 常駐中の PC の画面を表示する。画面を閉じても PC 側の録画を終了しない。 */
public final class MainActivity extends Activity {
    private WebView web;
    private TextView status;
    private ScrollView connectionGuide;
    private TextView guideAddress;
    private TextView automaticRetryHint;
    private static final int SURFACE = Color.rgb(35, 38, 43);
    private static final int TEXT = Color.rgb(241, 243, 245);
    private static final int MUTED = Color.rgb(181, 187, 196);
    private String base = "";
    private boolean active;
    private boolean disconnected = true;
    private int generation;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private final ExecutorService network = Executors.newSingleThreadExecutor();
    private final Runnable check = this::checkConnection;

    @SuppressWarnings("deprecation") // Android 8-10 の WindowInsets 互換経路。
    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(SURFACE);
        getWindow().setStatusBarColor(SURFACE);
        getWindow().setNavigationBarColor(SURFACE);
        root.setOnApplyWindowInsetsListener((view, insets) -> {
            view.setPadding(insets.getSystemWindowInsetLeft(), insets.getSystemWindowInsetTop(),
                    insets.getSystemWindowInsetRight(), insets.getSystemWindowInsetBottom());
            return insets;
        });
        LinearLayout bar = new LinearLayout(this);
        bar.setGravity(Gravity.CENTER_VERTICAL);
        Button connection = action("", this::showConnectionPanel);
        connection.setGravity(Gravity.CENTER_VERTICAL | Gravity.START);
        connection.setBackground(new RippleDrawable(ColorStateList.valueOf(0x22ffffff), null, null));
        status = connection;
        showConnectionStatus("接続確認中", 0xffe5b85c);
        connection.setSingleLine(true);
        bar.addView(connection, new LinearLayout.LayoutParams(0, -2, 1));
        root.addView(bar);
        View divider = new View(this);
        divider.setBackgroundColor(0xff40444c);
        root.addView(divider, new LinearLayout.LayoutParams(-1, dp(1)));
        connectionGuide = createConnectionGuide();
        connectionGuide.setVisibility(View.GONE);
        root.addView(connectionGuide, new LinearLayout.LayoutParams(-1, 0, 1));
        web = new WebView(this);
        web.getSettings().setJavaScriptEnabled(true);
        web.getSettings().setDomStorageEnabled(true);
        web.getSettings().setAllowFileAccess(false);
        web.getSettings().setAllowContentAccess(false);
        web.getSettings().setSupportMultipleWindows(true);
        web.setWebViewClient(new WebViewClient() {
            @Override public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                String url = request.getUrl().toString();
                if (LanAddress.sameOrigin(base, url)) return false;
                openExternal(url);
                return true;
            }
            @Override public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                if (request.isForMainFrame()) connectionFailed();
            }
        });
        web.setWebChromeClient(new WebChromeClient() {
            @Override public boolean onCreateWindow(WebView view, boolean dialog, boolean gesture, Message message) {
                if (!gesture) return false;
                WebView popup = new WebView(MainActivity.this);
                popup.setWebViewClient(new WebViewClient() {
                    @Override public boolean shouldOverrideUrlLoading(WebView ignored, WebResourceRequest request) {
                        String url = request.getUrl().toString();
                        if (LanAddress.sameOrigin(base, url)) web.loadUrl(url); else openExternal(url);
                        popup.destroy();
                        return true;
                    }
                });
                ((WebView.WebViewTransport) message.obj).setWebView(popup);
                message.sendToTarget();
                return true;
            }
        });
        root.addView(web, new LinearLayout.LayoutParams(-1, 0, 1));
        setContentView(root);
        base = getPreferences(MODE_PRIVATE).getString("server", "");
        connectionFailed();
    }

    private ScrollView createConnectionGuide() {
        LinearLayout guide = new LinearLayout(this);
        guide.setOrientation(LinearLayout.VERTICAL);
        guide.setPadding(dp(24), dp(28), dp(24), dp(28));
        guide.addView(label("PCへの接続を確認してください", 22, TEXT));
        addGuideStep(guide, "1  PCでSplatReplayを開く",
                "PCの電源を入れ、SplatReplayを起動してください。");
        addGuideStep(guide, "2  同じ自宅Wi-Fiにつなぐ",
                "スマホをPCと同じ自宅ネットワークに接続してください。PCは有線LANでも使えます。");
        addGuideStep(guide, "3  接続先を確認する",
                "PCのSplatReplayでLANアクセスを有効にし、表示されたURLと下の接続先を比べてください。違う場合は変更してください。");
        guideAddress = label("", 15, TEXT);
        guideAddress.setTextIsSelectable(true);
        guideAddress.setPadding(0, dp(12), 0, dp(12));
        guide.addView(guideAddress);
        guide.addView(action("接続先を変更", this::configure), new LinearLayout.LayoutParams(-1, -2));
        automaticRetryHint = label("", 14, MUTED);
        automaticRetryHint.setPadding(0, dp(28), 0, 0);
        guide.addView(automaticRetryHint);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(guide);
        return scroll;
    }

    private void addGuideStep(LinearLayout guide, String heading, String description) {
        TextView title = label(heading, 17, TEXT);
        title.setPadding(0, dp(24), 0, dp(8));
        guide.addView(title);
        guide.addView(label(description, 15, MUTED));
    }

    private void updateConnectionGuide() {
        guideAddress.setText(base.isEmpty() ? "接続先：未設定" : base);
        automaticRetryHint.setText(base.isEmpty()
                ? "接続先を設定すると、自動で接続を確認します。"
                : "確認が済んだら、この画面のままお待ちください。\n\n接続できない場合は5秒後に再確認します。接続できると自動でSplatReplayの画面に切り替わるため、再接続ボタンを押す必要はありません。");
    }

    private int dp(int value) { return Math.round(value * getResources().getDisplayMetrics().density); }

    private TextView label(String text, int size, int color) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextSize(size);
        view.setTextColor(color);
        return view;
    }

    private Button action(String text, Runnable run) {
        Button button = new Button(this);
        button.setText(text);
        button.setTextSize(14);
        button.setTextColor(TEXT);
        button.setAllCaps(false);
        button.setMinHeight(dp(48));
        button.setMinimumHeight(dp(48));
        button.setPadding(dp(16), dp(8), dp(16), dp(8));
        button.setStateListAnimator(null);
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(0xff343941);
        shape.setCornerRadius(dp(12));
        button.setBackground(new RippleDrawable(ColorStateList.valueOf(0x33ffffff), shape, null));
        button.setOnClickListener(view -> run.run());
        return button;
    }

    private void showConnectionStatus(String state, int color) {
        SpannableString text = new SpannableString("●PC" + state);
        text.setSpan(new ForegroundColorSpan(color), 0, 1, Spanned.SPAN_EXCLUSIVE_EXCLUSIVE);
        status.setText(text);
        status.setContentDescription("PC" + state + "。PC接続設定を開く");
    }

    private void retryConnection() {
        generation++;
        disconnected = true;
        showConnectionStatus("接続確認中", 0xffe5b85c);
        handler.removeCallbacks(check);
        checkConnection();
    }

    private void showConnectionPanel() {
        Dialog dialog = new Dialog(this);
        dialog.requestWindowFeature(Window.FEATURE_NO_TITLE);
        LinearLayout panel = new LinearLayout(this);
        panel.setOrientation(LinearLayout.VERTICAL);
        panel.setPadding(dp(24), dp(24), dp(24), dp(24));
        GradientDrawable background = new GradientDrawable();
        background.setColor(SURFACE);
        background.setCornerRadii(new float[]{dp(24), dp(24), dp(24), dp(24), 0, 0, 0, 0});
        panel.setBackground(background);
        LinearLayout heading = new LinearLayout(this);
        heading.setGravity(Gravity.CENTER_VERTICAL);
        heading.setPadding(0, 0, 0, dp(24));
        heading.addView(label("PC接続設定", 21, TEXT), new LinearLayout.LayoutParams(0, -2, 1));
        Button close = action("×", dialog::dismiss);
        close.setTextSize(24);
        close.setPadding(0, 0, 0, 0);
        close.setContentDescription("PC接続設定を閉じる");
        close.setBackground(new RippleDrawable(ColorStateList.valueOf(0x22ffffff), null, null));
        heading.addView(close, new LinearLayout.LayoutParams(dp(48), dp(48)));
        panel.addView(heading);
        panel.addView(label("接続先PC", 12, MUTED));
        TextView address = label(base.isEmpty() ? "未設定" : base, 16, TEXT);
        address.setTextIsSelectable(true);
        address.setPadding(0, dp(8), 0, dp(24));
        panel.addView(address);
        Button change = action("接続先を変更", () -> { dialog.dismiss(); configure(); });
        panel.addView(change, new LinearLayout.LayoutParams(-1, -2));
        Button reconnect = action("再接続", () -> { dialog.dismiss(); retryConnection(); });
        reconnect.setEnabled(!base.isEmpty());
        LinearLayout.LayoutParams spacing = new LinearLayout.LayoutParams(-1, -2);
        spacing.topMargin = dp(12);
        panel.addView(reconnect, spacing);
        ScrollView scroll = new ScrollView(this);
        scroll.addView(panel);
        dialog.setContentView(scroll);
        Window window = dialog.getWindow();
        window.setBackgroundDrawableResource(android.R.color.transparent);
        window.addFlags(WindowManager.LayoutParams.FLAG_DIM_BEHIND);
        window.setDimAmount(0.5f);
        window.setGravity(Gravity.BOTTOM);
        dialog.setCanceledOnTouchOutside(true);
        dialog.show();
        window.setLayout(-1, -2);
        panel.post(() -> {
            panel.setTranslationY(panel.getHeight());
            panel.animate().translationY(0).setDuration(200).start();
        });
    }

    private void configure() {
        EditText input = new EditText(this);
        input.setSingleLine(true);
        input.setInputType(android.text.InputType.TYPE_CLASS_TEXT | android.text.InputType.TYPE_TEXT_VARIATION_URI);
        input.setHint("http://192.168.1.10:8000");
        input.setText(base);
        AlertDialog dialog = new AlertDialog.Builder(this).setTitle("PCの接続先")
                .setMessage("SplatReplayのLANアクセス設定に表示されるURLを入力してください。")
                .setView(input).setPositiveButton("保存", null).setNegativeButton("キャンセル", null).create();
        dialog.setOnShowListener(ignored -> dialog.getButton(AlertDialog.BUTTON_POSITIVE).setOnClickListener(view -> {
            try {
                base = LanAddress.normalize(input.getText().toString());
                generation++;
                getPreferences(MODE_PRIVATE).edit().putString("server", base).apply();
                disconnected = true;
                updateConnectionGuide();
                dialog.dismiss();
                handler.removeCallbacks(check);
                checkConnection();
            } catch (IllegalArgumentException error) { input.setError(error.getMessage()); }
        }));
        dialog.show();
    }

    private void openExternal(String url) {
        Uri uri = Uri.parse(url);
        if (!("https".equals(uri.getScheme()) || "http".equals(uri.getScheme()))) return;
        try { startActivity(new Intent(Intent.ACTION_VIEW, uri)); }
        catch (android.content.ActivityNotFoundException error) { Toast.makeText(this, "外部ブラウザーを開けませんでした", Toast.LENGTH_LONG).show(); }
    }

    private void connectionFailed() {
        disconnected = true;
        web.setVisibility(View.GONE);
        showConnectionStatus("未接続", MUTED);
        updateConnectionGuide();
        connectionGuide.setVisibility(View.VISIBLE);
    }

    private void checkConnection() {
        if (!active || base.isEmpty()) return;
        if (disconnected) showConnectionStatus("接続確認中", 0xffe5b85c);
        String current = base;
        int currentGeneration = generation;
        network.execute(() -> {
            boolean ok = false;
            HttpURLConnection connection = null;
            try {
                connection = (HttpURLConnection) new URL(current + "api/health").openConnection();
                connection.setConnectTimeout(2000);
                connection.setReadTimeout(2000);
                connection.setInstanceFollowRedirects(false);
                ok = connection.getResponseCode() == 200;
            } catch (Exception ignored) { /* 接続不能の理由は断定しない。 */ }
            finally { if (connection != null) connection.disconnect(); }
            final boolean reachable = ok;
            handler.post(() -> {
                if (!active || currentGeneration != generation) return;
                if (reachable) {
                    if (disconnected) web.loadUrl(current);
                    disconnected = false;
                    web.setVisibility(View.VISIBLE);
                    showConnectionStatus("接続済", 0xff76d6a0);
                    connectionGuide.setVisibility(View.GONE);
                } else connectionFailed();
                handler.removeCallbacks(check);
                handler.postDelayed(check, 5000);
            });
        });
    }

    @Override protected void onResume() { super.onResume(); active = true; checkConnection(); }
    @Override protected void onPause() { active = false; generation++; handler.removeCallbacks(check); super.onPause(); }
    @Override protected void onDestroy() { network.shutdownNow(); web.destroy(); super.onDestroy(); }
    @SuppressWarnings("deprecation") // Android 8-12 の戻る操作にも対応する。
    @Override public void onBackPressed() { if (web.canGoBack()) web.goBack(); else super.onBackPressed(); }
}
