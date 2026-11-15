package cos.premy.mines;

import android.content.Context;
import android.os.Bundle;
import android.os.Parcel;
import android.util.Base64;

/** App-private primitive Bundle checkpoint, bounded and versioned; no external/untrusted data. */
public final class SessionStore {
    private static final String NAME="mine-session-v1";
    public static void save(Context context,Bundle state){
        Parcel p=Parcel.obtain();try{p.writeBundle(state);String s=Base64.encodeToString(p.marshall(),Base64.NO_WRAP);context.getSharedPreferences(NAME,0).edit().putString("session",s).apply();}finally{p.recycle();}
    }
    public static Bundle read(Context context){
        String s=context.getSharedPreferences(NAME,0).getString("session",null);if(s==null||s.length()>100000)return null;
        Parcel p=Parcel.obtain();try{byte[] a=Base64.decode(s,Base64.NO_WRAP);p.unmarshall(a,0,a.length);p.setDataPosition(0);return p.readBundle(SessionStore.class.getClassLoader());}catch(RuntimeException malformed){return null;}finally{p.recycle();}
    }
}
