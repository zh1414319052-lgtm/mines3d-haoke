package cos.premy.mines.online;

import android.content.Context;
import cos.premy.mines.BuildConfig;
import java.io.*;
import java.net.*;
import org.json.*;

/** Bounded HTTPS transport. No redirects, admin credentials, or hidden-board endpoints. */
public final class PlatformApi {
    public static final String ORIGIN="https://cleanbizai.com";
    public final String origin;
    private final PlatformSession session;
    private volatile String token;
    private volatile HttpURLConnection active;
    public static final class ApiError extends IOException{
        public final int status;public final String code;
        ApiError(int status,String code,String message){super(message);this.status=status;this.code=code;}
    }
    public PlatformApi(Context c,String requested){
        String o=ORIGIN;
        if(BuildConfig.DEBUG && requested!=null){
            try{URL u=new URL(requested);if("http".equals(u.getProtocol())&&("127.0.0.1".equals(u.getHost())||"10.0.2.2".equals(u.getHost()))&&u.getUserInfo()==null&&u.getQuery()==null)o=requested.replaceAll("/$","");}catch(Exception ignored){}
        }
        origin=o;session=new PlatformSession(c,origin);token=session.load();
    }
    public boolean signedIn(){return token!=null&&!token.isEmpty();}
    public void save(String value)throws Exception{session.save(value);token=value;}
    public void clear(){token="";session.clear();}
    public void cancel(){HttpURLConnection c=active;if(c!=null)c.disconnect();}
    public JSONObject call(String method,String path,JSONObject body)throws Exception{
        if(!path.startsWith("/api/")||path.contains(".."))throw new IOException("Invalid API path");
        HttpURLConnection c=(HttpURLConnection)new URL(origin+path).openConnection();active=c;
        try{
            c.setInstanceFollowRedirects(false);c.setConnectTimeout(10000);c.setReadTimeout(12000);c.setRequestMethod(method);
            c.setRequestProperty("Accept","application/json");c.setRequestProperty("User-Agent","Haoke-Mines3D/"+BuildConfig.VERSION_NAME);
            if(signedIn())c.setRequestProperty("Authorization","Bearer "+token);
            if(!"GET".equals(method)){byte[] data=(body==null?"{}":body.toString()).getBytes("UTF-8");c.setDoOutput(true);c.setRequestProperty("Content-Type","application/json; charset=utf-8");c.setFixedLengthStreamingMode(data.length);try(OutputStream out=c.getOutputStream()){out.write(data);}}
            int status=c.getResponseCode();if(status>=300&&status<400)throw new ApiError(status,"REDIRECT_REJECTED","Unexpected server redirect");
            InputStream input=status<400?c.getInputStream():c.getErrorStream();if(input==null)throw new IOException("Empty server response");
            ByteArrayOutputStream out=new ByteArrayOutputStream();try(InputStream in=input){byte[] b=new byte[8192];int n;while((n=in.read(b))!=-1){if(out.size()+n>512*1024)throw new IOException("Response too large");out.write(b,0,n);}}
            JSONObject result=new JSONObject(new String(out.toByteArray(),"UTF-8"));
            if(status>=400){JSONObject e=result.optJSONObject("error");String code=e==null?"HTTP_"+status:e.optString("code");if(status==401||"ACCOUNT_DISABLED".equals(code))clear();throw new ApiError(status,code,e==null?"Request failed":e.optString("message",code));}
            return result;
        }finally{c.disconnect();if(active==c)active=null;}
    }
    public JSONObject enter()throws Exception{return call("POST","/api/mines/enter",object("protocol",1,"build",BuildConfig.VERSION_CODE));}
    public static JSONObject object(Object... entries){JSONObject value=new JSONObject();try{for(int i=0;i<entries.length;i+=2)value.put((String)entries[i],entries[i+1]);}catch(JSONException e){throw new IllegalArgumentException(e);}return value;}
}
