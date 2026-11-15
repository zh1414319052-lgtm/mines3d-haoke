package cos.premy.mines;

import android.content.Context;
import android.content.res.Configuration;
import android.content.res.Resources;
import android.os.Build;
import android.support.v7.app.AppCompatActivity;

import java.util.Locale;

/** Keep app text tied to the first system language, independent of app or fallback locales. */
public abstract class LocalizedActivity extends AppCompatActivity {
    @Override
    protected void attachBaseContext(Context base) {
        super.attachBaseContext(withPrimaryLanguage(base, Resources.getSystem().getConfiguration()));
    }

    static Context withPrimaryLanguage(Context base, Configuration system) {
        Locale primary = Build.VERSION.SDK_INT >= 24
                ? (system.getLocales().isEmpty() ? null : system.getLocales().get(0))
                : system.locale;
        Configuration localized = new Configuration();
        localized.setLocale(supportedLocale(primary));
        return base.createConfigurationContext(localized);
    }

    static Locale supportedLocale(Locale primary) {
        return primary != null && "zh".equals(primary.getLanguage())
                ? Locale.SIMPLIFIED_CHINESE : Locale.ENGLISH;
    }
}
