package com.motify.wrapper.links

import android.content.Intent
import android.net.Uri
import com.google.firebase.dynamiclinks.FirebaseDynamicLinks
import kotlinx.coroutines.tasks.await

object DynamicLinkHandler {
    suspend fun resolve(intent: Intent?): Uri? {
        if (intent == null) return null
        return try {
            FirebaseDynamicLinks.getInstance().getDynamicLink(intent).await()?.link ?: intent.data
        } catch (_: Exception) {
            intent.data
        }
    }
}

