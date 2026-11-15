package cos.premy.mines.updates;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;
import org.json.JSONObject;
import org.junit.Test;
import static org.junit.Assert.*;

public class Mines3DFeedTest {
    @Test public void realRegisteredNoneFeedMatchesCompiledIdentityAndPin() throws Exception {
        try(InputStream in=getClass().getResourceAsStream("/updates/mines3d-none-v1.json")) {
            assertNotNull(in);byte[] raw=in.readAllBytes();
            JSONObject envelope=new JSONObject(new String(raw,StandardCharsets.UTF_8));
            JSONObject payload=new JSONObject(new String(Base64.getDecoder().decode(envelope.getString("payload")),StandardCharsets.UTF_8));
            long now=UpdateManifestValidator.utcDate(payload.get("issuedAt"))+1000;
            UpdateManifestValidator v=new UpdateManifestValidator(Collections.singletonMap(HaokeUpdateController.KEY_ID,Base64.getDecoder().decode(HaokeUpdateController.PUBLIC_KEY)));
            UpdateManifestValidator.Identity own=identity(UpdateAppIdentity.APPLICATION_ID,"stable");
            UpdateManifestValidator.Manifest m=v.verify(raw,own,now);
            assertEquals("none",m.status);assertEquals(0,m.revision);assertNull(m.release);
            assertThrows(UpdateManifestValidator.InvalidManifestException.class,()->v.verify(raw,identity(UpdateAppIdentity.APPLICATION_ID,"qa"),now));
            assertThrows(UpdateManifestValidator.InvalidManifestException.class,()->v.verify(raw,identity("cos.premy.mines.qa","stable"),now));
        }
    }
    private UpdateManifestValidator.Identity identity(String app,String channel){
        return new UpdateManifestValidator.Identity(HaokeUpdateController.SOFTWARE_ID,app,channel,20,
            "e1d81e7ee6b53804eb9f9a7d1444882a105aa07e67ccb396019a20aa5d644a7e",19,Collections.singletonList("armeabi-v7a"));
    }
}
