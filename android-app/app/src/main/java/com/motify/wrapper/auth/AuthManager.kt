package com.motify.wrapper.auth

import android.app.Activity
import com.google.android.gms.auth.api.signin.GoogleSignIn
import com.google.android.gms.auth.api.signin.GoogleSignInClient
import com.google.android.gms.auth.api.signin.GoogleSignInOptions
import com.google.firebase.auth.FirebaseAuth
import com.google.firebase.auth.GoogleAuthProvider
import com.motify.wrapper.R
import kotlinx.coroutines.tasks.await

class AuthManager(activity: Activity) {
    private val auth: FirebaseAuth = FirebaseAuth.getInstance()
    private val googleClient: GoogleSignInClient

    init {
        val options = GoogleSignInOptions.Builder(GoogleSignInOptions.DEFAULT_SIGN_IN)
            .requestIdToken(activity.getString(R.string.default_web_client_id))
            .requestEmail()
            .build()
        googleClient = GoogleSignIn.getClient(activity, options)
    }

    fun getSignInIntent() = googleClient.signInIntent

    suspend fun handleGoogleResult(accountIdToken: String) {
        val credential = GoogleAuthProvider.getCredential(accountIdToken, null)
        auth.signInWithCredential(credential).await()
    }

    suspend fun signOut() {
        auth.signOut()
        googleClient.signOut().await()
    }
}

