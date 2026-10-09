using System.Text;
using Nexus.PLM.Addin.Sdk.Translators;
using Nexus.PLM.Addin.Sdk.Translators.Testing;
using Xunit;

namespace Nexus.PLM.Inkscape.Translators.Tests;

/// <summary>Contract tests per translator.</summary>
public class SvgToPngContractTests : TranslatorContractTests<SvgToPngTranslator> { }

/// <summary>See <see cref="SvgToPngContractTests"/>.</summary>
public class SvgToPdfContractTests : TranslatorContractTests<SvgToPdfTranslator> { }

/// <summary>See <see cref="SvgToPngContractTests"/>.</summary>
public class SvgToJpegContractTests : TranslatorContractTests<SvgToJpegTranslator> { }

/// <summary>
/// Real end-to-end renders over an in-test fixture — these translators are pure .NET, so the
/// full conversion runs anywhere, which is exactly why Inkscape goes first in the example
/// rollout: it proves the pattern (and native Skia resolution) with no host install.
/// </summary>
public class SvgRenderingTests
{
    /// <summary>A 40×20 red rectangle on a transparent canvas.</summary>
    private const string Fixture =
        """<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="#ff0000"/></svg>""";

    private static Stream AsStream(string s) => new MemoryStream(Encoding.UTF8.GetBytes(s));

    private static async Task<byte[]> Run(ITranslator t, Stream input)
    {
        await using var output = await t.TranslateAsync(input);
        using var ms = new MemoryStream();
        await output.CopyToAsync(ms);
        return ms.ToArray();
    }

    [Fact]
    public async Task Png_HasThePngSignature()
    {
        var bytes = await Run(new SvgToPngTranslator(), AsStream(Fixture));

        Assert.True(bytes.Length > 8);
        Assert.Equal([0x89, (byte)'P', (byte)'N', (byte)'G'], bytes[..4]);
    }

    [Fact]
    public async Task Jpeg_HasTheJpegSignature()
    {
        var bytes = await Run(new SvgToJpegTranslator(), AsStream(Fixture));

        Assert.True(bytes.Length > 3);
        Assert.Equal([0xFF, 0xD8, 0xFF], bytes[..3]);
    }

    [Fact]
    public async Task Pdf_StartsWithThePdfHeader()
    {
        var bytes = await Run(new SvgToPdfTranslator(), AsStream(Fixture));

        Assert.True(bytes.Length > 5);
        Assert.Equal("%PDF-", Encoding.ASCII.GetString(bytes[..5]));
    }

    [Fact]
    public async Task GzippedSvgz_RendersToo()
    {
        // The catalog maps .svg AND .svgz to image/svg+xml, so gzipped bytes may arrive.
        using var packed = new MemoryStream();
        await using (var gz = new System.IO.Compression.GZipStream(packed, System.IO.Compression.CompressionMode.Compress, leaveOpen: true))
            await gz.WriteAsync(Encoding.UTF8.GetBytes(Fixture));
        packed.Position = 0;

        var bytes = await Run(new SvgToPngTranslator(), packed);

        Assert.Equal([0x89, (byte)'P', (byte)'N', (byte)'G'], bytes[..4]);
    }

    [Fact]
    public async Task NotAnSvg_FailsWithAnActionableMessage()
    {
        var ex = await Assert.ThrowsAsync<InvalidOperationException>(
            () => Run(new SvgToPngTranslator(), AsStream("just some text")));

        Assert.Contains("SVG", ex.Message);
    }
}

/// <summary>Repo-level rules.</summary>
public class InkscapeTranslatorSuiteTests
{
    private static readonly ITranslator[] All =
    [
        new SvgToPngTranslator(),
        new SvgToPdfTranslator(),
        new SvgToJpegTranslator(),
    ];

    /// <summary>The server's registry is first-wins on keys AND MIME pairs.</summary>
    [Fact]
    public void KeysAndMimePairsAreUniqueWithinTheRepo()
    {
        Assert.Equal(All.Length, All.Select(t => t.Key).Distinct().Count());
        Assert.Equal(All.Length, All.Select(t => (t.InputMimeType, t.OutputMimeType)).Distinct().Count());
    }

    /// <summary>The keys reserved in Nexus.PLM.Services/docs/translator-ownership.md.</summary>
    [Fact]
    public void CarriesTheThreeReservedKeys() =>
        Assert.Equal(
            ["svg_to_jpeg", "svg_to_pdf", "svg_to_png"],
            All.Select(t => t.Key).OrderBy(k => k).ToArray());

    /// <summary>This repo owns the svg-input family.</summary>
    [Fact]
    public void EveryTranslatorReadsSvg() =>
        Assert.All(All, t => Assert.Equal(MimeTypes.Svg, t.InputMimeType));
}
