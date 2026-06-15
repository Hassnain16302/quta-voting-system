// static/js/vote.js
document.addEventListener("DOMContentLoaded", async () => {
  const form = document.getElementById("vote-form");
  const statusBox = document.getElementById("metamask-status");

  // ✅ MetaMask is now optional — just show admin connection if needed
  if (window.ethereum) {
    try {
      const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
      const adminAccount = accounts[0];
      statusBox.classList.replace("alert-warning", "alert-success");
      statusBox.textContent = `✅ System ready. Admin wallet connected: ${adminAccount}`;
    } catch (err) {
      console.warn("MetaMask connection not required for voters.");
      statusBox.textContent = "ℹ️ Connected through secure backend.";
    }
  } else {
    statusBox.textContent = "ℹ️ Connected through backend (MetaMask optional).";
    statusBox.classList.replace("alert-warning", "alert-info");
  }

  // 🗳️ Voting form submission
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const selects = document.querySelectorAll("select");
    const votesMap = {};
    let hasSelection = false;

    selects.forEach((select) => {
      const designation = select.name.replace("vote_for_", "").replace(/_/g, " ");
      const cid = parseInt(select.value);
      if (cid && cid !== 0) {
        votesMap[designation] = cid;
        hasSelection = true;
      }
    });

    if (!hasSelection) {
      alert("⚠️ Please select at least one candidate before submitting.");
      return;
    }

    // 📨 Send selected votes to backend for blockchain submission
    try {
      const res = await fetch("/api/record_vote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ votes: votesMap }),
      });

      const result = await res.json();

      if (res.ok) {
        console.log("✅ Votes submitted:", result);
        alert("🎉 Your votes have been recorded successfully!");
        window.location.href = "/dashboard";
      } else {
        console.error("❌ Backend error:", result.error);
        alert("❌ Error: " + result.error);
      }
    } catch (error) {
      console.error("❌ Error submitting votes:", error);
      alert("Unexpected error: " + error.message);
    }
  });
});
