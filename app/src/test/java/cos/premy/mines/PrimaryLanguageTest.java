package cos.premy.mines;

import org.junit.Test;

import java.util.Locale;

import static org.junit.Assert.assertEquals;

public class PrimaryLanguageTest {
    @Test
    public void anyChineseVariantUsesSimplifiedChinese() {
        for (String tag : new String[]{"zh", "zh-CN", "zh-SG", "zh-Hant-HK", "zh-TW"}) {
            assertEquals(tag, Locale.SIMPLIFIED_CHINESE,
                    LocalizedActivity.supportedLocale(Locale.forLanguageTag(tag)));
        }
    }

    @Test
    public void otherLanguagesAndMissingLocaleUseEnglish() {
        for (String tag : new String[]{"en-US", "en-GB", "ja-JP", "es", "ru", "ar"}) {
            assertEquals(tag, Locale.ENGLISH,
                    LocalizedActivity.supportedLocale(Locale.forLanguageTag(tag)));
        }
        assertEquals(Locale.ENGLISH, LocalizedActivity.supportedLocale(null));
    }
}
