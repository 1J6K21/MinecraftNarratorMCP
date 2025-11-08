package name.minecraftmcp;

import net.fabricmc.api.ModInitializer;
import net.fabricmc.fabric.api.event.player.PlayerBlockBreakEvents;
import net.fabricmc.fabric.api.entity.event.v1.ServerLivingEntityEvents;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import net.minecraft.server.level.ServerPlayer;
import net.minecraft.world.damagesource.DamageSource;
import com.google.gson.Gson;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.Map;
import java.util.concurrent.CompletableFuture;

public class MinecraftMCP implements ModInitializer {
    public static final String MOD_ID = "minecraft-mcp";
    public static final Logger LOGGER = LoggerFactory.getLogger(MOD_ID);
    
    private static final HttpClient httpClient = HttpClient.newHttpClient();
    private static final Gson gson = new Gson();
    private static final String MCP_SERVER_URL = "http://localhost:8080/mcp";

    @Override
    public void onInitialize() {
        LOGGER.info("Minecraft MCP Mod Initialized!");
        
        // Block break events
        PlayerBlockBreakEvents.BEFORE.register((world, player, pos, state, blockEntity) -> {
            String blockName = state.getBlock().getName().getString();
            sendEventToMCP("block_broken", blockName);
            return true;
        });
        
        // Damage events
        ServerLivingEntityEvents.ALLOW_DAMAGE.register((entity, source, amount) -> {
            if (entity instanceof ServerPlayer) {
                String damageSource = source.getMsgId(); // e.g., "zombie", "fall", "lava"
                sendEventToMCP("damage_taken", damageSource);
            }
            return true;
        });
    }

    private void sendEventToMCP(String eventType, String eventSource) {
        CompletableFuture.runAsync(() -> {
            try {
                // New format: event_type and event_source
                Map<String, String> payload = Map.of(
                    "event_type", eventType,
                    "event_source", eventSource
                );
                
                String jsonPayload = gson.toJson(payload);
                
                HttpRequest request = HttpRequest.newBuilder()
                    .uri(URI.create(MCP_SERVER_URL))
                    .header("Content-Type", "application/json")
                    .POST(HttpRequest.BodyPublishers.ofString(jsonPayload))
                    .build();
                
                HttpResponse<String> response = httpClient.send(request, 
                    HttpResponse.BodyHandlers.ofString());
                
                LOGGER.info("Event sent: {} - {}", eventType, eventSource);
                
            } catch (Exception e) {
                LOGGER.warn("Failed to send event to MCP server: {}", e.getMessage());
            }
        });
    }
}
