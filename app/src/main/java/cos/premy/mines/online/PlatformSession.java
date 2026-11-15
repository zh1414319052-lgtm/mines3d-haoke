package cos.premy.mines.online;

import android.content.Context;
import android.os.Build;
import android.security.KeyPairGeneratorSpec;
import android.security.keystore.KeyGenParameterSpec;
import android.security.keystore.KeyProperties;
import android.util.Base64;
import java.math.BigInteger;
import java.security.KeyPairGenerator;
import java.security.KeyStore;
import java.util.Calendar;
import javax.crypto.Cipher;
import javax.security.auth.x500.X500Principal;

/** Player bearer only; RSA key remains in AndroidKeyStore (API 19+). No password storage.
 * API contracts: developer.android.com/reference/android/security/KeyPairGeneratorSpec.Builder
 * and developer.android.com/reference/android/security/keystore/KeyGenParameterSpec.Builder.
 */
public final class PlatformSession {
    private final Context context;private final String namespace;
    private static final String ALIAS="mines3d.player.session.v1";
    public PlatformSession(Context c,String origin){context=c.getApplicationContext();namespace="online-session-"+Integer.toHexString(origin.hashCode());}
    private KeyStore store()throws Exception{
        KeyStore s=KeyStore.getInstance("AndroidKeyStore");s.load(null);
        if(!s.containsAlias(ALIAS)){
            KeyPairGenerator g=KeyPairGenerator.getInstance("RSA","AndroidKeyStore");
            if(Build.VERSION.SDK_INT>=23){
                g.initialize(new KeyGenParameterSpec.Builder(ALIAS,KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setKeySize(2048).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_RSA_PKCS1).build());
            }else{
                Calendar from=Calendar.getInstance(),to=Calendar.getInstance();to.add(Calendar.YEAR,20);
                g.initialize(new KeyPairGeneratorSpec.Builder(context).setAlias(ALIAS).setKeySize(2048).setSubject(new X500Principal("CN=Mines3D player session")).setSerialNumber(BigInteger.ONE).setStartDate(from.getTime()).setEndDate(to.getTime()).build());
            }
            g.generateKeyPair();
        }return s;
    }
    public void save(String token)throws Exception{
        Cipher c=Cipher.getInstance("RSA/ECB/PKCS1Padding");c.init(Cipher.ENCRYPT_MODE,store().getCertificate(ALIAS).getPublicKey());
        String encrypted=Base64.encodeToString(c.doFinal(token.getBytes("UTF-8")),Base64.NO_WRAP);
        if(!context.getSharedPreferences(namespace,0).edit().putString("token",encrypted).commit())throw new java.io.IOException("Session storage failed");
    }
    public String load(){try{String value=context.getSharedPreferences(namespace,0).getString("token","");if(value.isEmpty())return "";Cipher c=Cipher.getInstance("RSA/ECB/PKCS1Padding");c.init(Cipher.DECRYPT_MODE,store().getKey(ALIAS,null));return new String(c.doFinal(Base64.decode(value,Base64.NO_WRAP)),"UTF-8");}catch(Exception ignored){clear();return "";}}
    public void clear(){context.getSharedPreferences(namespace,0).edit().clear().apply();}
}
