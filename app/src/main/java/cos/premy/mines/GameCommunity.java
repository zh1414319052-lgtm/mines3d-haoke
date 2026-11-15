package cos.premy.mines;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.ActivityNotFoundException;
import android.content.ClipData;
import android.content.ClipboardManager;
import android.content.Context;
import android.content.Intent;
import android.net.Uri;
import android.widget.Button;
import android.widget.LinearLayout;
import android.widget.Toast;

/** Player-initiated community actions. No account, room or session data is shared. */
public final class GameCommunity {
    // Both links were explicitly supplied by the owner on 2026-11-15.
    public static final String DOWNLOAD_URL = "https://www.haoke.org/software/491ec4cb67f1146b?platform=android";
    public static final String SHARE_URL = DOWNLOAD_URL;
    public static final String QQ_GROUP = "1841958554";

    private GameCommunity() {}
    private static String t(Context c, String zh, String en) { return MineTheme.tr(c, zh, en); }

    public static void addButtons(Activity activity, LinearLayout parent) {
        LinearLayout row = new LinearLayout(activity);
        Button share = MineTheme.button(activity, t(activity, "分享游戏", "Share game"), false);
        Button group = MineTheme.button(activity, t(activity, "加入 QQ 群", "Join QQ group") + "\n" + QQ_GROUP, false);
        share.setOnClickListener(v -> share(activity));
        group.setOnClickListener(v -> group(activity));
        row.addView(share, new LinearLayout.LayoutParams(0, -2, 1));
        LinearLayout.LayoutParams second = new LinearLayout.LayoutParams(0, -2, 1);
        second.leftMargin = MineTheme.dp(activity, 8);
        row.addView(group, second);
        LinearLayout.LayoutParams outer = new LinearLayout.LayoutParams(-1, -2);
        outer.topMargin = MineTheme.dp(activity, 12);
        parent.addView(row, outer);
    }

    private static void share(Activity activity) {
        MineTheme.dialog(new AlertDialog.Builder(activity)
                .setTitle(t(activity, "分享三维扫雷", "Share Mines 3D"))
                .setMessage(t(activity, "下载与分享链接", "Download and share link") + "\n" + SHARE_URL)
                .setPositiveButton(t(activity, "分享给好友", "Share with friends"), (d, w) -> {
                    Intent send = new Intent(Intent.ACTION_SEND).setType("text/plain")
                            .putExtra(Intent.EXTRA_SUBJECT, t(activity, "三维扫雷", "Mines 3D"))
                            .putExtra(Intent.EXTRA_TEXT, t(activity, "一起来玩三维扫雷！", "Play Mines 3D with me!") + "\n" + SHARE_URL);
                    try { activity.startActivity(Intent.createChooser(send, t(activity, "分享游戏", "Share game"))); }
                    catch (ActivityNotFoundException | SecurityException e) { copy(activity, SHARE_URL, t(activity, "链接已复制", "Link copied")); }
                })
                .setNeutralButton(t(activity, "复制链接", "Copy link"), (d, w) -> copy(activity, SHARE_URL, t(activity, "链接已复制", "Link copied")))
                .setNegativeButton(t(activity, "打开下载页", "Open download page"), (d, w) -> {
                    try { activity.startActivity(new Intent(Intent.ACTION_VIEW, Uri.parse(DOWNLOAD_URL))); }
                    catch (ActivityNotFoundException | SecurityException e) { copy(activity, DOWNLOAD_URL, t(activity, "无法打开浏览器，链接已复制", "No browser available; link copied")); }
                }).create());
    }

    private static void group(Activity activity) {
        MineTheme.dialog(new AlertDialog.Builder(activity)
                .setTitle(t(activity, "加入 QQ 群", "Join QQ group"))
                .setMessage(t(activity, "群号：", "Group: ") + QQ_GROUP + t(activity, "\n在 QQ 中确认加群，也可以复制群号搜索加入。", "\nConfirm in QQ, or copy the number and search for the group."))
                .setPositiveButton(t(activity, "打开 QQ", "Open QQ"), (d, w) -> {
                    Uri card = Uri.parse("mqqapi://card/show_pslcard?src_type=internal&version=1&uin=" + QQ_GROUP + "&card_type=group&source=qrcode");
                    try { activity.startActivity(new Intent(Intent.ACTION_VIEW, card).setPackage("com.tencent.mobileqq")); }
                    catch (ActivityNotFoundException | SecurityException e) {
                        MineTheme.dialog(new AlertDialog.Builder(activity)
                                .setTitle(t(activity, "复制群号加入", "Join with the group number"))
                                .setMessage(t(activity, "当前无法打开 QQ。请复制群号，在 QQ 中搜索加入：\n", "QQ could not be opened. Copy this number and search in QQ:\n") + QQ_GROUP)
                                .setPositiveButton(t(activity, "复制群号", "Copy group number"), (dialog, which) -> copy(activity, QQ_GROUP, t(activity, "群号已复制", "Group number copied")))
                                .setNegativeButton(t(activity, "关闭", "Close"), null).create());
                    }
                })
                .setNeutralButton(t(activity, "复制群号", "Copy group number"), (d, w) -> copy(activity, QQ_GROUP, t(activity, "群号已复制", "Group number copied")))
                .setNegativeButton(t(activity, "返回", "Back"), null).create());
    }

    private static void copy(Activity activity, String value, String success) {
        ClipboardManager clipboard = (ClipboardManager) activity.getSystemService(Context.CLIPBOARD_SERVICE);
        if (clipboard == null) { Toast.makeText(activity, t(activity, "无法访问剪贴板", "Clipboard unavailable"), Toast.LENGTH_SHORT).show(); return; }
        try {
            clipboard.setPrimaryClip(ClipData.newPlainText("Mines 3D", value));
            Toast.makeText(activity, success, Toast.LENGTH_SHORT).show();
        } catch (SecurityException e) {
            Toast.makeText(activity, t(activity, "系统不允许复制，请手动记录", "Copying is blocked; note the value manually"), Toast.LENGTH_LONG).show();
        }
    }
}
