using System.Security.Cryptography;
using System.Security.Cryptography.X509Certificates;

var store = new X509Store(StoreName.My, StoreLocation.CurrentUser);
store.Open(OpenFlags.ReadOnly);

var cert = store.Certificates
                .Find(X509FindType.FindBySubjectName, "Ihab Abadi", false)[0];

byte[] data = System.Text.Encoding.UTF8.GetBytes("Hello");
byte[] signature;

using (var csp = cert.GetRSAPrivateKey())
{
    signature = csp.SignData(data, HashAlgorithmName.SHA256, RSASignaturePadding.Pkcs1);
}
